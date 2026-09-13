import * as path from "path";
import {
  Stack,
  StackProps,
  Duration,
  RemovalPolicy,
  CfnOutput,
  Annotations,
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
 *   invoke {intake_id}
 *        |
 *        v
 *   pde_handoff (Forensic)
 *     1. get Hub tracking item        --cross-account dynamodb:GetItem-->  Hub table
 *     2. recompute + verify sha256     --s3:GetObject-->  Forensic artifact bucket
 *     3. FAIL-CLOSED gate: push iff human_decision=='accepted' AND hash verified
 *     4. (only if push)                --s3:PutObject (one prefix)-->  Sandbox bucket
 *     5. ALWAYS record outcome         --sqs:SendMessage-->  Hub ingest queue (RD-013)
 *
 * RD-047 CONTRACT-FIRST decision: the trigger is a RECORDED HUMAN ACCEPT
 * (`human_decision == "accepted"` on the Hub tracking item), NEVER the advisory
 * `recommended_verdict` (RD-040). It is FAIL-CLOSED: absent a genuine accept, or on
 * any hash mismatch, NOTHING leaves Forensic. The pushed artifact goes
 * Forensic -> Sandbox DIRECTLY; it NEVER transits the Hub (only the bounded,
 * verdict-free handoff OUTCOME crosses to the Hub via the existing RD-013 gate).
 * ZTIE never re-executes the artifact (security clearance only). The push MECHANISM
 * is decoupled from the human accept/reject UI + the automatic decision-event
 * trigger, which are Story 4.4.
 *
 * Least privilege (RD-047): the pusher role gets EXACTLY:
 *   * cross-account `dynamodb:GetItem` on the Hub tracking table (read the decision
 *     + the authoritative sha256; READ-only — never writes to the Hub table);
 *   * `s3:GetObject` on the Forensic artifact bucket (read the raw body to hash +
 *     push);
 *   * `s3:PutObject` (+ tagging) on EXACTLY ONE prefix of the Sandbox landing
 *     bucket (the Sandbox bucket policy ALSO grants this — belt-and-suspenders
 *     both-ends least-privilege);
 *   * `sqs:SendMessage` on EXACTLY the one Hub ingest queue (cross the outcome).
 * NO Bedrock. NO write to any Hub data store. NO broader S3.
 */

const FORENSIC_ACCOUNT_ID = "360999005254";

export interface ZtiePdeHandoffStackProps extends StackProps {
  /**
   * Name of the Forensic artifact S3 bucket the raw body lives in (intake output
   * `ArtifactBucketName`). The pusher reads the artifact from here to hash + push.
   */
  readonly artifactBucketName: string;
  /**
   * Name of the Hub durable tracking DynamoDB table (Hub output
   * `TrackingTableName`). The pusher reads the recorded human decision + sha256
   * from here CROSS-ACCOUNT (GetItem only).
   */
  readonly hubTrackingTableName: string;
  /**
   * ARN of the Hub durable tracking DynamoDB table (used to scope the cross-account
   * `dynamodb:GetItem` grant to exactly that one table). Build it from the Hub
   * account id + region + table name:
   * `arn:aws:dynamodb:<region>:641628980935:table/<TrackingTableName>`.
   */
  readonly hubTrackingTableArn: string;
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
    // PURE gate + envelope logic (handoff.py) + a thin boto3 seam (awsio.py); no
    // third-party runtime dep, so a plain zip asset suffices (no Docker bundling).
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
      ),
      // Reads a bounded artifact (~6 MB cap) + one cross-account get + one
      // cross-account put + one send. Generous but bounded headroom.
      timeout: Duration.seconds(60),
      memorySize: 256,
      logGroup: handoffLogGroup,
      environment: {
        TRACKING_TABLE: props.hubTrackingTableName,
        ARTIFACT_BUCKET: props.artifactBucketName,
        SANDBOX_LANDING_BUCKET: props.sandboxLandingBucket,
        SANDBOX_LANDING_PREFIX: sandboxLandingPrefix,
        SANDBOX_ACCOUNT_ID: sandboxAccountId,
        // The same one-directional Forensic -> Hub door every derived envelope uses.
        HUB_INGEST_QUEUE_URL: props.hubIngestQueueUrl,
        // Story 4.6 (RD-047): the handoff outcome pins its OWN contract version so it
        // validates independently of the shared CONTRACT_VERSION. Set explicitly so a
        // Forensic redeploy carries the pin alongside the bundled
        // handoff.contract.v1.json (the deploy-gap lesson — ship the contract).
        HANDOFF_CONTRACT_VERSION: "1.0",
        LOG_LEVEL: "INFO",
      },
    });

    // --- Least-privilege grants (RD-047) -----------------------------------
    // (1) Cross-account READ of the Hub tracking item (the decision + sha256).
    //     GetItem ONLY on exactly the one Hub table; never a write to the Hub.
    handoffFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "ReadHubTrackingItemCrossAccount",
        effect: iam.Effect.ALLOW,
        actions: ["dynamodb:GetItem"],
        resources: [props.hubTrackingTableArn],
      }),
    );

    // (2) Read the raw artifact body from the Forensic artifact bucket (in-account)
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

    // (3) Push the artifact CROSS-ACCOUNT to EXACTLY one prefix of the Sandbox
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

    // (4) Cross the bounded, verdict-free handoff outcome to the Hub via EXACTLY the
    //     one Hub ingest queue. SendMessage only (the RD-013 one-directional door).
    handoffFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SendHandoffOutcomeToHubIngestQueue",
        effect: iam.Effect.ALLOW,
        actions: ["sqs:SendMessage"],
        resources: [props.hubIngestQueueArn],
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
