import * as path from "path";
import {
  Stack,
  StackProps,
  Duration,
  Size,
  RemovalPolicy,
  CfnOutput,
  Annotations,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import { SqsEventSource } from "aws-cdk-lib/aws-lambda-event-sources";

/**
 * ZTIE Story 2.1 — the static-analysis lane (Forensic account, 360999005254).
 *
 * The non-executing static-scan compute. It consumes the Forensic static-scan work
 * queue (produced by the intake stack's preprocessor when routing names the
 * `static_analysis` lane), runs the four static tools (cfn-lint, cfn-guard, checkov,
 * bandit) over the raw artifact READ FROM the Forensic artifact bucket, writes the
 * full normalized findings document back to that bucket under `findings/` (RD-009 —
 * it stays in Forensic), and crosses only a bounded, derived SUMMARY to the Hub
 * ingest queue via the RD-013 gate (the fifth envelope kind).
 *
 *   [static-scan work queue] --(consume)--> [static-scan Lambda (container image)]
 *        (intra-Forensic)                          |        |
 *                                    read artifact  |        |  write findings/ (Forensic S3)
 *                                                   |        |
 *                                                   |        └─ sqs:SendMessage (summary)
 *                                                   |               -> Hub ingest queue (RD-013)
 *                                                   └─ NON-EXECUTING: parses the artifact, never runs it
 *
 * PACKAGING (RD-021): a CONTAINER-IMAGE Lambda. Three tools are pip packages;
 * cfn-guard is a Rust binary — an image is the clean way to ship both. The
 * no-Docker rule (RD-001) is SPECIFICALLY about the dynamic DETONATION host (where
 * a container would distort behavioral telemetry); it does NOT apply to packaging
 * the non-executing static scanners.
 *
 * Zero-trust: the raw artifact + full findings document never leave Forensic; only
 * the bounded summary crosses. The summary carries no verdict — a scan is EVIDENCE.
 *
 * This stack has TWO cross-stack imports, both in the Forensic account (no
 * cross-account resolution): the artifact bucket + the static-scan work queue from
 * the intake stack, and the Hub ingest queue ARN (from the Hub stack output). They
 * are supplied via context so the stack deploys independently with Forensic creds.
 */

const FORENSIC_ACCOUNT_ID = "360999005254";

export interface ZtieStaticScanStackProps extends StackProps {
  /** Forensic artifact bucket name (intake stack output `ArtifactBucketName`). */
  readonly artifactBucketName: string;
  /** Forensic static-scan work queue URL (intake output `StaticScanQueueUrl`). */
  readonly staticScanQueueUrl: string;
  /** Forensic static-scan work queue ARN (intake output `StaticScanQueueArn`). */
  readonly staticScanQueueArn: string;
  /** Hub ingest queue URL (Hub stack output `IngestQueueUrl`) — summary crosses here. */
  readonly hubIngestQueueUrl: string;
  /** Hub ingest queue ARN (Hub stack output `IngestQueueArn`) — scopes the send grant. */
  readonly hubIngestQueueArn: string;
  /** cfn-guard binary version baked into the image (Dockerfile ARG). */
  readonly cfnGuardVersion?: string;
}

export class ZtieStaticScanStack extends Stack {
  /** The static-scan Lambda's role ARN — register it as a Hub-queue sender. */
  public readonly staticScanRoleArn: string;

  constructor(scope: Construct, id: string, props: ZtieStaticScanStackProps) {
    super(scope, id, props);

    // Guard: this lane touches the raw artifact, so it belongs in Forensic (RD-008).
    if (props?.env?.account && props.env.account !== FORENSIC_ACCOUNT_ID) {
      Annotations.of(this).addWarning(
        `ZTIE static-scan lane is intended for the Forensic account ` +
          `${FORENSIC_ACCOUNT_ID} (it reads the raw artifact, RD-008); deploying ` +
          `into ${props.env.account}. Confirm this is intentional.`,
      );
    }

    // --- Imports (all in the Forensic account) -----------------------------
    const artifactBucket = s3.Bucket.fromBucketName(
      this,
      "ImportedArtifactBucket",
      props.artifactBucketName,
    );
    const staticScanQueue = sqs.Queue.fromQueueArn(
      this,
      "ImportedStaticScanQueue",
      props.staticScanQueueArn,
    );

    // --- Lambda: the static-scan lane (CONTAINER IMAGE, RD-021) ------------
    // The image bundles the four tools + the handler; see lambdas/static_scan/
    // Dockerfile. It is NON-EXECUTING — the tools parse the artifact as data.
    // OD-003: explicit LogGroup replaces the deprecated `logRetention` prop.
    const staticScanLogGroup = new logs.LogGroup(
      this,
      "StaticScanFunctionLogGroup",
      {
        retention: logs.RetentionDays.ONE_MONTH,
        removalPolicy: RemovalPolicy.DESTROY,
      },
    );
    const staticScanFn = new lambda.DockerImageFunction(
      this,
      "StaticScanFunction",
      {
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "..", "..", "lambdas", "static_scan"),
          {
            buildArgs: props.cfnGuardVersion
              ? { CFN_GUARD_VERSION: props.cfnGuardVersion }
              : undefined,
          },
        ),
        // The four tools (checkov especially) are memory + CPU hungry; give headroom.
        memorySize: 2048,
        // Below the work queue's 360s visibility timeout; four tools + downloads.
        timeout: Duration.seconds(300),
        // Ephemeral local storage for the downloaded artifact + tool scratch.
        ephemeralStorageSize: Size.mebibytes(1024),
        logGroup: staticScanLogGroup,
        environment: {
          // The one-directional Forensic -> Hub door (same queue as the other
          // envelopes). Only the bounded summary crosses here.
          HUB_INGEST_QUEUE_URL: props.hubIngestQueueUrl,
          // Story 2.2 bumped the summary contract to 1.1 (signature-scan tool +
          // compliance roll-up). Story 2.2G bumps it to 1.2 (adds the 'gitleaks'
          // tool — the SOLE secret scanner, superseding the 2.2 SECRET regex). The
          // lane emits 1.2. The Hub ingest stack MUST be redeployed to accept 1.2
          // BEFORE this lane is redeployed (deploy-gap: else the summary quarantines).
          SUMMARY_CONTRACT_VERSION: "1.2",
          FINDINGS_PREFIX: "findings/",
          PER_TOOL_TIMEOUT_S: "120",
          LOG_LEVEL: "INFO",
        },
      },
    );
    this.staticScanRoleArn = staticScanFn.role!.roleArn;

    // Consume the Forensic static-scan work queue.
    staticScanFn.addEventSource(
      new SqsEventSource(staticScanQueue, {
        // One artifact per invocation keeps a slow/failing scan isolated.
        batchSize: 1,
        reportBatchItemFailures: true,
      }),
    );

    // --- Least-privilege grants --------------------------------------------
    // Read the raw artifact it scans + write the findings document back under
    // findings/ (both in the Forensic artifact bucket — the document STAYS in
    // Forensic, RD-009). grantReadWrite covers head/get + put.
    artifactBucket.grantRead(staticScanFn);
    artifactBucket.grantPut(staticScanFn, "findings/*");

    // The imported bucket is KMS-encrypted (KMS_MANAGED). grant* adds the S3
    // actions; aws/s3 managed-key decrypt/generate is covered for the account
    // principal. (No customer-managed key to grant here.)

    // Cross to the Hub: EXACTLY sqs:SendMessage on EXACTLY the one Hub ingest
    // queue (least-privilege, one-directional, RD-013). No other Hub access.
    staticScanFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SendStaticScanSummaryToHubIngestQueue",
        effect: iam.Effect.ALLOW,
        actions: ["sqs:SendMessage"],
        resources: [props.hubIngestQueueArn],
      }),
    );

    // --- Outputs -----------------------------------------------------------
    new CfnOutput(this, "StaticScanFunctionName", {
      value: staticScanFn.functionName,
      description:
        "Static-scan lane Lambda name (Story 2.1). Tail its logs to see per-tool status + findings counts per intake_id.",
    });
    new CfnOutput(this, "StaticScanRoleArn", {
      value: this.staticScanRoleArn,
      description:
        "Static-scan Lambda execution role ARN. Pass as forensicStaticScanRoleArn to the Hub stack so it is the THIRD send-only principal on the Hub ingest queue (tightest least-privilege).",
    });
  }
}
