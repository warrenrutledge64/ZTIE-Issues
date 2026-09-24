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
 * ZTIE Story 4.7 (RD-047, per RD-048/RD-049) — the Forensic-side REJECT/destroy
 * mechanism (the sibling of 4.6's ACCEPT-push).
 *
 * This stack deploys into the **Forensic** account (360999005254) — the blast zone
 * where the raw artifact + its detonation chamber live. It stands up the
 * `pde_reject` Lambda: the REJECT/hold ENFORCEMENT ACTION. Invoked on demand by
 * `intake_id`, it enforces the human-REJECT gate and, on a genuine Hub-signed
 * `rejected` token + a verified sha256, DESTROYS the raw artifact (all S3 versions +
 * delete-markers under intake/<id>/) AND its derived Forensic outputs (findings/ runs/
 * traces/ for the intake) AND terminates any live detonation chamber (the ephemeral
 * EC2, if still running — explicit, not the 5-min hard TTL). On INCONCLUSIVE (no
 * rejected token) it HOLDS. Either way it crosses a bounded, verdict-free disposition
 * OUTCOME to the Hub; the derived report in the Hub always survives.
 *
 *   invoke {intake_id, decision_token, signature, artifact_s3_key}
 *        |
 *        v
 *   pde_reject (Forensic)
 *     1. VERIFY the Hub-signed decision_token OFFLINE (cryptography, embedded public
 *        key), expected_decision="rejected" — NO call into the Hub / Hub KMS
 *        (RD-048/RD-049). A missing token => the INCONCLUSIVE HOLD (fail-safe default)
 *     2. recompute the artifact sha256  --s3:GetObject-->  Forensic artifact bucket
 *     3. FAIL-SAFE gate: destroy iff the signature verifies AND decision=='rejected'
 *        AND token.sha256 == recomputed sha256 AND fresh AND trusted key_id
 *     4. (only if destroy) delete ALL versions + markers under the intake prefixes
 *        --s3:DeleteObject/ListBucketVersions--> Forensic artifact bucket, AND
 *        --ec2:DescribeInstances/TerminateInstances--> terminate any live chamber
 *     5. ALWAYS record outcome          --sqs:SendMessage-->  Hub ingest queue (RD-013)
 *
 * **Trust model (RD-048/RD-049):** the trigger is NOT a cross-account read of the
 * Hub's `human_decision`. The Hub is STRICTLY the control plane and hands out an
 * authenticated `decision.token.v1` (a KMS-asymmetric-signed decision) that this spoke
 * VERIFIES OFFLINE against the Hub's embedded PUBLIC key — the Hub is never read (no
 * `dynamodb:GetItem`, no Hub KMS call). It is FAIL-SAFE: absent a valid Hub-signed
 * `rejected` token bound to the recomputed artifact bytes (fresh, trusted key),
 * NOTHING is destroyed. The advisory `recommended_verdict` (RD-040) is never involved;
 * an unsigned/spoke-asserted decision cannot pass. The destroy happens IN Forensic;
 * only the bounded, verdict-free disposition OUTCOME crosses via the RD-013 gate. ZTIE
 * never re-executes the artifact. The destroy MECHANISM is decoupled from the human
 * accept/reject UI + the one-directional Hub->Forensic decision delivery, which are
 * Story 4.4 (for now the signed token arrives in the invoke payload).
 *
 * Least privilege (RD-048/RD-049): the destroyer role gets EXACTLY:
 *   * `s3:GetObject` on the intake/ prefix (read the raw body to recompute the sha256);
 *   * `s3:DeleteObject` on the intake's prefixes (raw + derived: intake/ findings/
 *     runs/ traces/) to destroy ALL object versions + delete-markers;
 *   * `s3:ListBucketVersions` on the artifact bucket (enumerate every version + marker
 *     to delete — a versioned bucket needs this, the OD-001 lesson);
 *   * `ec2:DescribeInstances` (find a live chamber; Describe cannot be resource-scoped)
 *     + `ec2:TerminateInstances` scoped by a condition to the ZTIE ephemeral tag (can
 *     only ever terminate a ZTIE ephemeral detonation host, never anything else);
 *   * `sqs:SendMessage` on EXACTLY the one Hub ingest queue (cross the outcome).
 * NO `dynamodb` (no Hub read — RD-048). NO Bedrock. NO write to any Hub data store.
 * The Hub's signing PUBLIC key is embedded as an env var at deploy (not a secret) so
 * verification is OFFLINE. The Lambda is DOCKER-BUNDLED because it verifies the ECDSA
 * signature with `cryptography` (not in the Lambda runtime) — same bundling mechanism
 * the pde_handoff pusher + hub_ingest validator use.
 */

const FORENSIC_ACCOUNT_ID = "360999005254";

export interface ZtieForensicRejectStackProps extends StackProps {
  /**
   * Name of the Forensic artifact S3 bucket the raw body + derived outputs live in
   * (intake output `ArtifactBucketName`). The destroyer reads the artifact from here
   * to recompute the sha256, then destroys the intake's prefixes.
   */
  readonly artifactBucketName: string;
  /**
   * The Hub decision-signing PUBLIC key, PEM-encoded (from `aws kms get-public-key`
   * on the `ZtieDecisionSigningStack` key, wrapped in PEM). Embedded so the destroyer
   * verifies the signed decision token OFFLINE (RD-048/RD-049) — the Hub is never
   * called. NOT a secret. Multi-line PEM is fine as an env var (the fragility is
   * passing it through `-c`; bin/ztie-infra.ts decodes a single-line base64 form).
   */
  readonly hubPublicKeyPem: string;
  /**
   * The trusted signing key id(s) — the decision token's `key_id` must be one of
   * these. Comma-separated to allow a rotation window (accept old + new). Typically
   * the Hub signing key ARN (`ZtieDecisionSigningStack` output `DecisionSigningKeyArn`).
   */
  readonly trustedKeyIds: string;
  /**
   * URL of the Hub-owned ingest SQS queue (Hub output `IngestQueueUrl`). The destroyer
   * sends the derived, verdict-free disposition outcome envelope here (the RD-013 door).
   */
  readonly hubIngestQueueUrl: string;
  /**
   * ARN of the same Hub ingest queue (Hub output `IngestQueueArn`). Scopes the
   * destroyer's `sqs:SendMessage` grant to exactly that one queue (least-privilege).
   */
  readonly hubIngestQueueArn: string;
}

export class ZtieForensicRejectStack extends Stack {
  constructor(
    scope: Construct,
    id: string,
    props: ZtieForensicRejectStackProps,
  ) {
    super(scope, id, props);

    // Guard: the destroyer + the raw artifact + the chamber must be in Forensic (the
    // blast zone) — never the Hub. A synth-time annotation, not a hard failure.
    if (props?.env?.account && props.env.account !== FORENSIC_ACCOUNT_ID) {
      Annotations.of(this).addWarning(
        `ZTIE Forensic REJECT/destroy Lambda is intended for the Forensic account ` +
          `${FORENSIC_ACCOUNT_ID} (the blast zone where the raw artifact + chamber ` +
          `live, RD-009/RD-047); deploying into ${props.env.account}. The Hub must ` +
          `never touch the raw payload. Confirm this is intentional.`,
      );
    }

    // --- Lambda: the Forensic REJECT/destroy mechanism ----------------------
    // Verifies a Hub-signed decision.token.v1 OFFLINE (RD-048/RD-049) with
    // expected_decision="rejected", which needs the `cryptography` ECDSA verify — NOT
    // in the Lambda runtime. So the asset is DOCKER-BUNDLED (pip-install `cryptography`
    // into the package, the same mechanism the pde_handoff pusher uses). Local pip is
    // avoided because `cryptography` ships a compiled native extension that must match
    // the Lambda Python 3.12 manylinux runtime.
    // OD-003: explicit LogGroup (not the deprecated logRetention prop).
    const rejectLogGroup = new logs.LogGroup(this, "PdeRejectLogGroup", {
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: RemovalPolicy.DESTROY,
    });
    const rejectFn = new lambda.Function(this, "PdeReject", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "..", "..", "lambdas", "pde_reject"),
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
      // Recomputes a bounded artifact sha256 + verifies a signature + lists/deletes
      // the intake's object versions + describes/terminates a chamber + one send.
      // Generous but bounded headroom.
      timeout: Duration.seconds(120),
      memorySize: 256,
      logGroup: rejectLogGroup,
      environment: {
        ARTIFACT_BUCKET: props.artifactBucketName,
        // The same one-directional Forensic -> Hub door every derived envelope uses.
        HUB_INGEST_QUEUE_URL: props.hubIngestQueueUrl,
        // RD-048/RD-049: the Hub's decision-signing PUBLIC key (PEM), embedded so the
        // destroyer verifies OFFLINE (no call into the Hub / Hub KMS). NOT a secret.
        HUB_PUBLIC_KEY_PEM: props.hubPublicKeyPem,
        // The trusted signing key id(s) the token's key_id must match (a set, for
        // rotation). Typically the Hub signing key ARN.
        TRUSTED_KEY_IDS: props.trustedKeyIds,
        // Story 4.7 (RD-047): the disposition outcome pins its OWN contract version so
        // it validates independently of the shared CONTRACT_VERSION. Set explicitly so
        // a Forensic redeploy carries the pin alongside the bundled
        // disposition.contract.v1.json (the deploy-gap lesson — ship the contract).
        DISPOSITION_CONTRACT_VERSION: "1.0",
        LOG_LEVEL: "INFO",
      },
    });

    // --- Least-privilege grants (RD-048/RD-049) ----------------------------
    // NOTE (RD-048): there is deliberately NO `dynamodb` grant and NO Hub read of any
    // kind — the decision arrives as a Hub-signed token verified OFFLINE against the
    // embedded public key. The destroyer never calls the Hub.
    //
    // (1) Read the raw artifact body from the intake/ prefix (in-account) to recompute
    //     the sha256 for the token's artifact-binding check. GetObject only.
    rejectFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "ReadForensicArtifactBody",
        effect: iam.Effect.ALLOW,
        actions: ["s3:GetObject"],
        resources: [`arn:aws:s3:::${props.artifactBucketName}/intake/*`],
      }),
    );

    // (2) Destroy ALL object versions + delete-markers under the intake's prefixes
    //     (raw + derived). DeleteObject + DeleteObjectVersion, scoped to the four
    //     ZTIE per-intake prefixes only — never the whole bucket. The versioned bucket
    //     requires deleting every version (the OD-001 lesson); GetObjectVersion lets
    //     the delete address specific versions.
    rejectFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "DestroyForensicIntakePrefixes",
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

    // (3) List every object VERSION under the intake's prefixes (a versioned-bucket
    //     delete must enumerate Versions[] + DeleteMarkers[]). ListBucket +
    //     ListBucketVersions are bucket-level actions (cannot be object-scoped), so
    //     scope them to the bucket ARN and constrain the prefix via a condition.
    rejectFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "ListForensicArtifactVersions",
        effect: iam.Effect.ALLOW,
        actions: ["s3:ListBucket", "s3:ListBucketVersions"],
        resources: [`arn:aws:s3:::${props.artifactBucketName}`],
        conditions: {
          StringLike: {
            "s3:prefix": ["intake/*", "findings/*", "runs/*", "traces/*"],
          },
        },
      }),
    );

    // (4) Find a live detonation chamber for the intake. ec2:DescribeInstances does
    //     NOT support resource-level scoping (it is a list/describe action), so it is
    //     granted on "*"; the handler filters by the ZTIE ephemeral tags so it only
    //     ever ACTS on a ZTIE ephemeral host.
    rejectFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "DescribeInstancesToFindChamber",
        effect: iam.Effect.ALLOW,
        actions: ["ec2:DescribeInstances"],
        resources: ["*"],
      }),
    );

    // (5) Terminate the live chamber. Scoped by a condition to instances carrying the
    //     ZTIE ephemeral tag (Ephemeral=true) — so this grant can NEVER terminate a
    //     non-ephemeral / non-ZTIE instance even if the handler filter were bypassed.
    //     Belt-and-suspenders with the handler's tag:IntakeId + tag:Ephemeral filter.
    rejectFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "TerminateEphemeralChamberOnly",
        effect: iam.Effect.ALLOW,
        actions: ["ec2:TerminateInstances"],
        resources: ["*"],
        conditions: {
          StringEquals: {
            "aws:ResourceTag/Ephemeral": "true",
            "aws:ResourceTag/Project": "ZTIE",
          },
        },
      }),
    );

    // (6) Cross the bounded, verdict-free disposition outcome to the Hub via EXACTLY
    //     the one Hub ingest queue. SendMessage only (the RD-013 one-directional door).
    rejectFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SendDispositionOutcomeToHubIngestQueue",
        effect: iam.Effect.ALLOW,
        actions: ["sqs:SendMessage"],
        resources: [props.hubIngestQueueArn],
      }),
    );

    // --- Outputs (used by the deploy + live-validation handoff) -------------
    new CfnOutput(this, "PdeRejectFunctionName", {
      value: rejectFn.functionName,
      description:
        "Story 4.7 Forensic REJECT/destroy Lambda name (RD-047). Invoke with {intake_id, decision_token, signature} to enforce the REJECT gate + destroy the artifact (all versions) + its derived Forensic outputs + terminate any live chamber. FAIL-SAFE: no verified rejected token => HOLD, nothing destroyed.",
    });
    new CfnOutput(this, "PdeRejectRoleArn", {
      value: rejectFn.role!.roleArn,
      description:
        "Forensic REJECT/destroy Lambda execution role ARN. Least-privilege: s3 read/delete on the intake prefixes + ec2 describe/terminate (ZTIE ephemeral tag only) + sqs send to the Hub ingest queue. NO dynamodb (no Hub read, RD-048).",
    });
  }
}
