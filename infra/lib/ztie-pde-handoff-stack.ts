import * as path from "path";
import {
  Stack,
  StackProps,
  Duration,
  RemovalPolicy,
  CfnOutput,
  Annotations,
  DockerImage,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";

/**
 * ZTIE Story 4.6 (RD-047) — the Forensic-side ACCEPT-push (PDE handoff) mechanism.
 *
 * This stack deploys into the **Forensic** account (360999005254) — the blast zone
 * where the raw artifact lives. It stands up the `pde_handoff` Lambda: the ACCEPT
 * ENFORCEMENT ACTION. Invoked on demand by `intake_id`, it enforces the human-ACCEPT
 * gate and, on a genuine accept + a verified sha256, PUSHES the artifact
 * one-directionally + least-privilege to the Pipeline-Sandbox landing bucket
 * (586917955591). On landing the artifact is under PDE control and ZTIE's job ends.
 *
 *   invoke {intake_id, decision_token, signature, artifact_s3_key}
 *        |
 *        v
 *   pde_handoff (Forensic)
 *     1. VERIFY the Hub-signed decision_token OFFLINE (cryptography, embedded public
 *        key) — NO call into the Hub / Hub KMS (RD-048/RD-049)
 *     2. recompute the artifact sha256  --s3:GetObject-->  Forensic artifact bucket
 *     3. FAIL-CLOSED gate: push iff the signature verifies AND decision=='accepted'
 *        AND token.sha256 == recomputed sha256 AND fresh AND trusted key_id
 *     4. (only if push)                 --s3:PutObject (one prefix)-->  Sandbox bucket
 *     5. ALWAYS record outcome          --sqs:SendMessage-->  Hub ingest queue (RD-013)
 *
 * **REWORK (RD-048/RD-049):** the trigger is no longer a cross-account read of the
 * Hub's `human_decision`. The Hub is STRICTLY the control plane and hands out an
 * authenticated `decision.token.v1` (a KMS-asymmetric-signed decision) that this
 * spoke VERIFIES OFFLINE against the Hub's embedded PUBLIC key — the Hub is never
 * read (no `dynamodb:GetItem`, no Hub KMS call). It is FAIL-CLOSED: absent a valid
 * Hub-signed `accepted` token bound to the recomputed artifact bytes (fresh, trusted
 * key), NOTHING leaves Forensic. The advisory `recommended_verdict` (RD-040) is never
 * involved; an unsigned/spoke-asserted decision cannot pass. The pushed artifact goes
 * Forensic -> Sandbox DIRECTLY; it NEVER transits the Hub (only the bounded,
 * verdict-free handoff OUTCOME crosses via the RD-013 gate). ZTIE never re-executes
 * the artifact. The push MECHANISM is decoupled from the human accept/reject UI + the
 * one-directional Hub->Forensic decision delivery, which are Story 4.4 (for now the
 * signed token arrives in the invoke payload).
 *
 * Least privilege (RD-048/RD-049): the pusher role gets EXACTLY:
 *   * `s3:GetObject` on the Forensic artifact bucket (read the raw body to hash +
 *     push);
 *   * `s3:PutObject` (+ tagging) on EXACTLY ONE prefix of the Sandbox landing bucket
 *     (the Sandbox bucket policy ALSO grants this — both-ends least-privilege);
 *   * `sqs:SendMessage` on EXACTLY the one Hub ingest queue (cross the outcome).
 * NO `dynamodb` (no Hub read — RD-048). NO Bedrock. NO write to any Hub data store.
 * The Hub's signing PUBLIC key is embedded as an env var at deploy (not a secret) so
 * verification is OFFLINE. The Lambda is DOCKER-BUNDLED because it verifies the ECDSA
 * signature with `cryptography` (not in the Lambda runtime) — same bundling mechanism
 * the hub_ingest validator uses for jsonschema.
 */

const FORENSIC_ACCOUNT_ID = "360999005254";

export interface ZtiePdeHandoffStackProps extends StackProps {
  /**
   * Name of the Forensic artifact S3 bucket the raw body lives in (intake output
   * `ArtifactBucketName`). The pusher reads the artifact from here to hash + push.
   */
  readonly artifactBucketName: string;
  /**
   * The Hub decision-signing PUBLIC key, PEM-encoded (from `aws kms get-public-key`
   * on the `ZtieDecisionSigningStack` key, wrapped in PEM). Embedded so the pusher
   * verifies the signed decision token OFFLINE (RD-048/RD-049) — the Hub is never
   * called. NOT a secret. Multi-line PEM is fine as an env var.
   */
  readonly hubPublicKeyPem: string;
  /**
   * The trusted signing key id(s) — the decision token's `key_id` must be one of
   * these. Comma-separated to allow a rotation window (accept old + new). Typically
   * the Hub signing key ARN (`ZtieDecisionSigningStack` output `DecisionSigningKeyArn`).
   */
  readonly trustedKeyIds: string;
  /**
   * URL of the Hub-owned ingest SQS queue (Hub output `IngestQueueUrl`). The pusher
   * sends the derived, verdict-free handoff outcome envelope here (the RD-013 door).
   */
  readonly hubIngestQueueUrl: string;
  /**
   * ARN of the same Hub ingest queue (Hub output `IngestQueueArn`). Scopes the
   * pusher's `sqs:SendMessage` grant to exactly that one queue (least-privilege).
   */
  readonly hubIngestQueueArn: string;
  /**
   * Name of the Pipeline-Sandbox landing bucket (Sandbox output
   * `SandboxLandingBucketName`) the artifact is pushed to cross-account.
   */
  readonly sandboxLandingBucket: string;
  /**
   * The Pipeline-Sandbox account id the artifact lands in (recorded in the handoff
   * outcome). Default 586917955591.
   */
  readonly sandboxAccountId?: string;
  /**
   * The single key prefix the pusher writes under on the Sandbox bucket. Default
   * `accepted/`. MUST match the Sandbox landing stack's `landingPrefix`.
   */
  readonly sandboxLandingPrefix?: string;
}

export class ZtiePdeHandoffStack extends Stack {
  constructor(scope: Construct, id: string, props: ZtiePdeHandoffStackProps) {
    super(scope, id, props);

    // Guard: the pusher + the raw artifact must be in Forensic (the blast zone) —
    // never the Hub. A synth-time annotation, not a hard failure.
    if (props?.env?.account && props.env.account !== FORENSIC_ACCOUNT_ID) {
      Annotations.of(this).addWarning(
        `ZTIE PDE-handoff pusher is intended for the Forensic account ` +
          `${FORENSIC_ACCOUNT_ID} (the blast zone where the raw artifact lives, ` +
          `RD-009/RD-047); deploying into ${props.env.account}. The Hub must never ` +
          `touch the raw payload. Confirm this is intentional.`,
      );
    }

    const sandboxAccountId = props.sandboxAccountId ?? "586917955591";
    let sandboxLandingPrefix = props.sandboxLandingPrefix ?? "accepted/";
    if (!sandboxLandingPrefix.endsWith("/")) {
      sandboxLandingPrefix += "/";
    }

    // --- Lambda: the Forensic PDE-handoff pusher ---------------------------
    // The REWORK verifies a Hub-signed decision.token.v1 OFFLINE (RD-048/RD-049),
    // which needs the `cryptography` ECDSA verify — NOT in the Lambda runtime. So the
    // asset is DOCKER-BUNDLED (pip-install `cryptography` into the package, the same
    // mechanism the hub_ingest validator uses for jsonschema/rpds-py). Local pip is
    // avoided because `cryptography` ships a compiled native extension that must match
    // the Lambda Python 3.12 manylinux runtime.
    // OD-003: explicit LogGroup (not the deprecated logRetention prop).
    const handoffLogGroup = new logs.LogGroup(this, "PdeHandoffLogGroup", {
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: RemovalPolicy.DESTROY,
    });
    const handoffFn = new lambda.Function(this, "PdeHandoff", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "..", "..", "lambdas", "pde_handoff"),
        {
          bundling: {
            image: DockerImage.fromRegistry(
              "public.ecr.aws/lambda/python:3.12",
            ),
            entrypoint: ["bash", "-c"],
            command: [
              [
                // Platform-correct prebuilt wheels for the Lambda runtime so the
                // `cryptography` native extension imports cleanly at runtime.
                "pip install --no-cache-dir " +
                  "--platform manylinux2014_x86_64 " +
                  "--implementation cp --python-version 3.12 " +
                  "--only-binary=:all: --upgrade " +
                  "-r requirements.txt -t /asset-output",
                "cp -r . /asset-output",
              ].join(" && "),
            ],
          },
        },
      ),
      // Reads a bounded artifact (~6 MB cap) + verifies a signature + one
      // cross-account put + one send. Generous but bounded headroom.
      timeout: Duration.seconds(60),
      memorySize: 256,
      logGroup: handoffLogGroup,
      environment: {
        ARTIFACT_BUCKET: props.artifactBucketName,
        SANDBOX_LANDING_BUCKET: props.sandboxLandingBucket,
        SANDBOX_LANDING_PREFIX: sandboxLandingPrefix,
        SANDBOX_ACCOUNT_ID: sandboxAccountId,
        // The same one-directional Forensic -> Hub door every derived envelope uses.
        HUB_INGEST_QUEUE_URL: props.hubIngestQueueUrl,
        // RD-048/RD-049: the Hub's decision-signing PUBLIC key (PEM), embedded so the
        // pusher verifies OFFLINE (no call into the Hub / Hub KMS). NOT a secret.
        HUB_PUBLIC_KEY_PEM: props.hubPublicKeyPem,
        // The trusted signing key id(s) the token's key_id must match (a set, for
        // rotation). Typically the Hub signing key ARN.
        TRUSTED_KEY_IDS: props.trustedKeyIds,
        // Story 4.6 (RD-047): the handoff outcome pins its OWN contract version so it
        // validates independently of the shared CONTRACT_VERSION. Set explicitly so a
        // Forensic redeploy carries the pin alongside the bundled
        // handoff.contract.v1.json (the deploy-gap lesson — ship the contract).
        HANDOFF_CONTRACT_VERSION: "1.0",
        // Story 4.10 (RD-059): the intake's Forensic prefixes swept on a VERIFIED accept
        // AFTER the artifact lands in the Sandbox (raw intake/ + derived findings/ runs/
        // traces/). Comma-separated templates with {intake_id}. This ENABLES the
        // post-accept sweep; a blank value disables it (backward-compatible push-only).
        FORENSIC_SWEEP_PREFIX_TEMPLATES:
          "intake/{intake_id}/,findings/{intake_id}/,runs/{intake_id}/,traces/{intake_id}/",
        LOG_LEVEL: "INFO",
      },
    });

    // --- Least-privilege grants (RD-048/RD-049) ----------------------------
    // NOTE (RD-048): there is deliberately NO `dynamodb` grant and NO Hub read of any
    // kind — the decision arrives as a Hub-signed token verified OFFLINE against the
    // embedded public key. The pusher never calls the Hub.
    //
    // (1) Read the raw artifact body from the Forensic artifact bucket (in-account)
    //     to recompute the sha256 + read the bytes to push. GetObject only, scoped
    //     to the intake/ prefix (where raw bodies live).
    handoffFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "ReadForensicArtifactBody",
        effect: iam.Effect.ALLOW,
        actions: ["s3:GetObject"],
        resources: [`arn:aws:s3:::${props.artifactBucketName}/intake/*`],
      }),
    );

    // (2) Push the artifact CROSS-ACCOUNT to EXACTLY one prefix of the Sandbox
    //     landing bucket. PutObject (+ tagging) only; nothing broader. The Sandbox
    //     bucket policy grants the reciprocal side (both-ends least-privilege).
    handoffFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "PushArtifactToSandboxLandingPrefixOnly",
        effect: iam.Effect.ALLOW,
        actions: ["s3:PutObject", "s3:PutObjectTagging"],
        resources: [
          `arn:aws:s3:::${props.sandboxLandingBucket}/${sandboxLandingPrefix}*`,
        ],
      }),
    );

    // (3) Cross the bounded, verdict-free handoff outcome to the Hub via EXACTLY the
    //     one Hub ingest queue. SendMessage only (the RD-013 one-directional door).
    handoffFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SendHandoffOutcomeToHubIngestQueue",
        effect: iam.Effect.ALLOW,
        actions: ["sqs:SendMessage"],
        resources: [props.hubIngestQueueArn],
      }),
    );

    // (4) Story 4.10 (RD-059): the POST-ACCEPT Forensic SWEEP. On a verified accept that
    //     landed in the Sandbox, destroy the intake's Forensic residue so a human ACCEPT
    //     leaves the blast zone as clean as a human REJECT (Story 4.7). Least-privilege,
    //     mirroring the reject destroyer EXACTLY: DeleteObject/DeleteObjectVersion on the
    //     intake's raw + derived prefixes ONLY (never the whole bucket), and the
    //     bucket-level ListBucket/ListBucketVersions needed to enumerate every version +
    //     delete-marker. This deletes the intake's OBJECTS only — the bucket + VPC + roles
    //     + launch template are untouched (RD-012: destroy ephemeral state, keep the infra).
    handoffFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SweepForensicIntakePrefixesOnAccept",
        effect: iam.Effect.ALLOW,
        actions: [
          "s3:DeleteObject",
          "s3:DeleteObjectVersion",
          "s3:GetObjectVersion",
        ],
        resources: [
          `arn:aws:s3:::${props.artifactBucketName}/intake/*`,
          `arn:aws:s3:::${props.artifactBucketName}/findings/*`,
          `arn:aws:s3:::${props.artifactBucketName}/runs/*`,
          `arn:aws:s3:::${props.artifactBucketName}/traces/*`,
        ],
      }),
    );
    // ListBucket / ListBucketVersions are BUCKET-level actions (cannot be object-scoped),
    // so they target the bucket ARN; the sweep still deletes only the four intake prefixes.
    handoffFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "ListForensicArtifactVersionsForSweep",
        effect: iam.Effect.ALLOW,
        actions: ["s3:ListBucket", "s3:ListBucketVersions"],
        resources: [`arn:aws:s3:::${props.artifactBucketName}`],
      }),
    );

    // --- Outputs (used by the two-account deploy + live-validation handoff) --
    new CfnOutput(this, "PdeHandoffFunctionName", {
      value: handoffFn.functionName,
      description:
        "Story 4.6 Forensic PDE-handoff pusher Lambda name (RD-047). Invoke with {intake_id} to enforce the ACCEPT gate + push a hash-verified accepted artifact to the Pipeline-Sandbox landing bucket. FAIL-CLOSED: no recorded human accept / hash mismatch => no push.",
    });
    new CfnOutput(this, "PdeHandoffRoleArn", {
      value: handoffFn.role!.roleArn,
      description:
        "Forensic PDE-handoff pusher Lambda execution role ARN. Pass as forensicPusherRoleArn to the Pipeline-Sandbox ZtieSandboxLandingStack for the tightest cross-account PutObject grant (least-privilege, RD-047).",
    });
  }
}
