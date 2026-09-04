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
import * as s3 from "aws-cdk-lib/aws-s3";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as s3n from "aws-cdk-lib/aws-s3-notifications";
import * as sqs from "aws-cdk-lib/aws-sqs";

/**
 * ZTIE Story 1.1 (+ 1.1R remediation) — Intake gateway.
 *
 * POST /intake (API Gateway REST, IAM/SigV4 auth) -> intake Lambda (Python 3.12)
 * -> raw artifact body persisted to an encrypted, versioned, block-public S3
 * bucket **in Forensic**, then a DERIVED, contract-shaped tracking envelope is
 * emitted across the one-directional Forensic -> Hub boundary via the Hub-owned
 * ingest SQS queue.
 *
 * Story 1.1R (RD-012 / RD-013): there is **no durable DynamoDB in Forensic** any
 * more. Forensic holds only ephemeral state (the raw artifact S3 body). The
 * authoritative, durable tracking record lives in the **Hub** and is written by
 * the Hub-owned validating gate, only after the envelope passes the enforced data
 * contract. This stack grants the intake Lambda exactly one cross-account
 * permission: `sqs:SendMessage` on the Hub ingest queue. It gets NO write to any
 * Hub data store.
 *
 * Zero-trust: nothing here classifies, marks safe, or forwards an artifact.
 * IAM auth gates who may submit; the envelope status is always RECEIVED and the
 * verdict is never asserted here (it is Hub-owned).
 *
 * Topology (RD-008/009): this stack deploys into the Forensic account
 * (360999005254). The raw artifact body (S3) stays in Forensic — the blast zone.
 * No raw payload ever crosses to the Hub; only derived metadata crosses, and only
 * through the contract gate.
 */

/**
 * Forensic account (360999005254) — ZTIE self-contained + ultimate blast-radius
 * containment (RD-008/009). Intake and the raw artifact body (S3) live HERE and
 * stay HERE. Per RD-012 there is no durable store in Forensic; the durable record
 * is in the Hub, written by the Hub validating gate over the RD-013 data contract.
 */
const FORENSIC_ACCOUNT_ID = "360999005254";

export interface ZtieIntakeStackProps extends StackProps {
  /**
   * URL of the Hub-owned ingest SQS queue (from the ZtieHubTrackingStack output
   * `IngestQueueUrl`). The intake Lambda sends the derived tracking envelope here.
   */
  readonly hubIngestQueueUrl: string;
  /**
   * ARN of the same Hub ingest queue. Used to scope the intake Lambda's
   * `sqs:SendMessage` grant to exactly that one queue (least-privilege, RD-013).
   */
  readonly hubIngestQueueArn: string;
}

export class ZtieIntakeStack extends Stack {
  constructor(scope: Construct, id: string, props: ZtieIntakeStackProps) {
    super(scope, id, props);

    // Guard: warn loudly if this is not being deployed into the Forensic account.
    // ZTIE (intake + raw payload) must be self-contained in Forensic — the blast
    // zone — never the Hub. (A synth-time annotation, not a hard failure, so
    // `cdk synth` still works in an account-less/CI context.)
    if (props?.env?.account && props.env.account !== FORENSIC_ACCOUNT_ID) {
      Annotations.of(this).addWarning(
        `ZTIE intake is intended for the Forensic account ${FORENSIC_ACCOUNT_ID} ` +
          `(ZTIE self-contained + blast-radius containment, RD-008); deploying into ` +
          `${props.env.account}. The Hub must never store the raw payload. ` +
          `Confirm this is intentional.`,
      );
    }

    // --- S3: artifact body store -------------------------------------------
    const artifactBucket = new s3.Bucket(this, "IntakeArtifactBucket", {
      encryption: s3.BucketEncryption.KMS_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      versioned: true,
      removalPolicy: RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          // Bound cost: expire noncurrent versions; the intake record in
          // DynamoDB is the durable index into the current object.
          noncurrentVersionExpiration: Duration.days(90),
          abortIncompleteMultipartUploadAfter: Duration.days(7),
        },
      ],
    });

    // NOTE (RD-012): there is intentionally NO durable DynamoDB table in this
    // stack. The durable tracking record lives in the Hub (ZtieHubTrackingStack)
    // and is written by the Hub validating gate over the RD-013 data contract.
    // Forensic holds only ephemeral state (the raw artifact S3 body above).

    // --- Lambda: intake handler --------------------------------------------
    const intakeFn = new lambda.Function(this, "IntakeHandler", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "..", "..", "lambdas", "intake"),
      ),
      timeout: Duration.seconds(30),
      memorySize: 256,
      logRetention: logs.RetentionDays.ONE_MONTH,
      environment: {
        ARTIFACT_BUCKET: artifactBucket.bucketName,
        // The Hub-owned ingest queue — the one-directional Forensic -> Hub door.
        HUB_INGEST_QUEUE_URL: props.hubIngestQueueUrl,
        FORENSIC_ACCOUNT_ID,
        CONTRACT_VERSION: "1.0",
        LOG_LEVEL: "INFO",
        // ~6 MB decoded, safely under API Gateway's ~10 MB request cap.
        MAX_ARTIFACT_BYTES: String(6 * 1024 * 1024),
      },
    });

    // Least-privilege: write raw artifact bodies to the Forensic S3 bucket, and
    // send the derived tracking envelope to EXACTLY the one Hub ingest queue.
    // No write to any Hub data store (RD-013: one-directional, least-privilege).
    artifactBucket.grantPut(intakeFn);
    intakeFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SendTrackingEnvelopeToHubIngestQueue",
        effect: iam.Effect.ALLOW,
        actions: ["sqs:SendMessage"],
        resources: [props.hubIngestQueueArn],
      }),
    );

    // --- SQS: the Forensic static-scan work queue (Story 2.1) --------------
    // An INTRA-FORENSIC work queue: the preprocessor enqueues a static-scan JOB
    // here when the routing decision names the static_analysis lane, and the
    // Story 2.1 static-scan Lambda (a separate stack, ZtieStaticScanStack) consumes
    // it. This is NOT a Forensic -> Hub crossing (both ends are in Forensic); the
    // job carries only the artifact's Forensic S3 coordinates. The static-scan
    // Lambda later crosses a derived summary to the Hub via the RD-013 gate.
    //
    // The queue is created HERE (with the preprocessor + artifact bucket) so the
    // producer wiring is local; the static-scan stack imports it by URL/ARN via
    // context. Both ends stay in the Forensic account.
    const staticScanDlq = new sqs.Queue(this, "StaticScanDlq", {
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      enforceSSL: true,
      retentionPeriod: Duration.days(14),
    });
    const staticScanQueue = new sqs.Queue(this, "StaticScanQueue", {
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      enforceSSL: true,
      // Must be >= the static-scan Lambda timeout (the container Lambda runs the
      // four tools; give it headroom). The static-scan stack sets a matching
      // function timeout below this.
      visibilityTimeout: Duration.seconds(360),
      retentionPeriod: Duration.days(4),
      deadLetterQueue: { queue: staticScanDlq, maxReceiveCount: 3 },
    });

    // --- SQS: the Forensic detonation work queue (Story 2.3) ---------------
    // The DYNAMIC-lane counterpart to the static-scan work queue. The preprocessor
    // enqueues a detonation JOB here when the routing decision names the
    // dynamic_detonation lane, and the Story 2.3 detonation Lambda (a separate
    // stack, ZtieDetonationStack) consumes it. Like the static queue this is an
    // INTRA-FORENSIC hand-off (both ends in Forensic); the job carries only the
    // artifact's Forensic S3 coordinates, and the detonation lane later crosses a
    // bounded, verdict-free run OUTCOME to the Hub via the RD-013 gate.
    const detonationDlq = new sqs.Queue(this, "DetonationDlq", {
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      enforceSSL: true,
      retentionPeriod: Duration.days(14),
    });
    const detonationQueue = new sqs.Queue(this, "DetonationQueue", {
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      enforceSSL: true,
      // Must be >= the detonation Lambda timeout. The detonation orchestrator
      // launches an ephemeral EC2, waits for SSM Online, runs host-native, and
      // observes teardown — give it generous headroom. The detonation stack sets a
      // matching function timeout below this.
      visibilityTimeout: Duration.seconds(900),
      retentionPeriod: Duration.days(4),
      // Fewer redeliveries than the static lane: a detonation launches real EC2, so
      // a poison job should DLQ quickly rather than repeatedly spinning up hosts.
      deadLetterQueue: { queue: detonationDlq, maxReceiveCount: 2 },
    });

    // --- Lambda: preprocessor classifier + router (Story 1.2 + 1.3) --------
    // Runs downstream of intake, in Forensic. Triggered by ObjectCreated on the
    // artifact bucket, it reads a bounded HEAD slice of the raw body (the read
    // stays in Forensic), runs the PURE classifier, then the PURE router over the
    // resulting class label, and emits TWO DERIVED envelopes to the SAME Hub
    // ingest queue the intake handler uses: (1) the classification LABEL (Story
    // 1.2) and (2) the routing DECISION (Story 1.3 — the plan of which Phase-2
    // lane(s) apply). The Hub validating gate enforces each contract by envelope
    // kind and upserts onto the durable tracking record (keyed by intake_id).
    //
    // Zero-trust: the raw body never leaves Forensic (only derived data crosses);
    // neither envelope carries a verdict / forward-to-PDE / safety field — a
    // classification is a LABEL and a routing decision is a PLAN OF CONTROLS. The
    // verdict stays Hub-side / human-gated (Phase 4). The two Phase-2 lanes
    // (static_analysis, dynamic_detonation) and the safe-reject entry (Story 1.4)
    // are the addressable fork targets the routing decision names.
    const preprocessorFn = new lambda.Function(this, "PreprocessorHandler", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "..", "..", "lambdas", "preprocessor"),
      ),
      timeout: Duration.seconds(30),
      memorySize: 256,
      logRetention: logs.RetentionDays.ONE_MONTH,
      environment: {
        // Same one-directional Forensic -> Hub door as intake.
        HUB_INGEST_QUEUE_URL: props.hubIngestQueueUrl,
        CLASSIFICATION_CONTRACT_VERSION: "1.0",
        // Story 1.3: the routing-decision envelope (a third kind on the same
        // gate). The preprocessor emits BOTH the classification label and the
        // routing decision (plan of controls) derived from that label.
        ROUTING_CONTRACT_VERSION: "1.0",
        // Story 1.4: the safe-reject outcome envelope (a fourth kind). Emitted
        // when the router says the artifact is unroutable (routable=false).
        REJECT_CONTRACT_VERSION: "1.0",
        // Story 2.1: the Forensic static-scan work queue. When routing names the
        // static_analysis lane, the preprocessor enqueues a static-scan job here
        // (intra-Forensic hand-off, not a Hub crossing).
        STATIC_SCAN_QUEUE_URL: staticScanQueue.queueUrl,
        // Story 2.3: the Forensic detonation work queue. When routing names the
        // dynamic_detonation lane, the preprocessor enqueues a detonation job here
        // (intra-Forensic hand-off, not a Hub crossing).
        DETONATION_QUEUE_URL: detonationQueue.queueUrl,
        LOG_LEVEL: "INFO",
        // Only the head slice is inspected (matches the classifier bound).
        CLASSIFY_HEAD_BYTES: String(64 * 1024),
      },
    });

    // Least-privilege: read the artifact body it classifies (head + ranged get),
    // and send the derived label + routing decision to EXACTLY the one Hub ingest
    // queue (both envelopes use the same send-only grant). No write to any Hub
    // data store (RD-013: one-directional, least-privilege).
    artifactBucket.grantRead(preprocessorFn);
    preprocessorFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SendClassificationEnvelopeToHubIngestQueue",
        effect: iam.Effect.ALLOW,
        actions: ["sqs:SendMessage"],
        resources: [props.hubIngestQueueArn],
      }),
    );
    // Story 2.1: the preprocessor may enqueue a static-scan job onto the Forensic
    // static-scan work queue (intra-Forensic). Least-privilege: SendMessage only.
    staticScanQueue.grantSendMessages(preprocessorFn);
    // Story 2.3: the preprocessor may also enqueue a detonation job onto the
    // Forensic detonation work queue (intra-Forensic). Least-privilege: SendMessage.
    detonationQueue.grantSendMessages(preprocessorFn);

    // Trigger classification when a raw artifact lands under the intake/ prefix.
    // (The intake handler writes keys as intake/<intake_id>/<filename>.)
    artifactBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(preprocessorFn),
      { prefix: "intake/" },
    );

    // --- API Gateway: POST /intake (IAM/SigV4 auth) ------------------------
    const api = new apigateway.RestApi(this, "IntakeApi", {
      restApiName: "ztie-intake",
      description: "ZTIE intake gateway — POST /intake (IAM auth).",
      deployOptions: {
        stageName: "prod",
        throttlingRateLimit: 50,
        throttlingBurstLimit: 20,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        metricsEnabled: true,
      },
      // Allow larger binary bodies to pass through as-is.
      binaryMediaTypes: ["application/octet-stream"],
      minCompressionSize: undefined,
    });

    const intakeResource = api.root.addResource("intake");
    intakeResource.addMethod(
      "POST",
      new apigateway.LambdaIntegration(intakeFn, { proxy: true }),
      {
        // Component-to-component auth: callers SigV4-sign with an AWS principal
        // that holds execute-api:Invoke. Cognito is deferred to the Phase 4
        // human-facing dashboard.
        authorizationType: apigateway.AuthorizationType.IAM,
      },
    );

    // --- Outputs (used by the live-validation handoff) ---------------------
    new CfnOutput(this, "IntakeEndpoint", {
      value: `${api.url}intake`,
      description: "POST endpoint for artifact intake (SigV4-signed).",
    });
    new CfnOutput(this, "ArtifactBucketName", {
      value: artifactBucket.bucketName,
      description:
        "Forensic S3 bucket holding raw intake artifact bodies (and, under findings/, the Story 2.1 normalized findings documents). Pass as artifactBucketName to the static-scan stack.",
    });
    new CfnOutput(this, "StaticScanQueueUrl", {
      value: staticScanQueue.queueUrl,
      description:
        "Forensic static-scan work queue URL (Story 2.1). Pass as staticScanQueueUrl to the static-scan stack (its Lambda consumes this queue).",
    });
    new CfnOutput(this, "StaticScanQueueArn", {
      value: staticScanQueue.queueArn,
      description:
        "Forensic static-scan work queue ARN (Story 2.1). Pass as staticScanQueueArn to the static-scan stack.",
    });
    new CfnOutput(this, "DetonationQueueUrl", {
      value: detonationQueue.queueUrl,
      description:
        "Forensic detonation work queue URL (Story 2.3). Pass as detonationQueueUrl to the detonation stack (its Lambda consumes this queue).",
    });
    new CfnOutput(this, "DetonationQueueArn", {
      value: detonationQueue.queueArn,
      description:
        "Forensic detonation work queue ARN (Story 2.3). Pass as detonationQueueArn to the detonation stack.",
    });
    new CfnOutput(this, "IntakeHandlerRoleArn", {
      value: intakeFn.role!.roleArn,
      description:
        "Intake Lambda execution role ARN. Pass as forensicIntakeRoleArn to the Hub stack for tightest send-only grant.",
    });
    new CfnOutput(this, "PreprocessorFunctionName", {
      value: preprocessorFn.functionName,
      description:
        "Preprocessor classifier + router Lambda name (Story 1.2 + 1.3). Tail its logs to see the classification label AND the routing decision (lanes) per intake_id.",
    });
    new CfnOutput(this, "PreprocessorRoleArn", {
      value: preprocessorFn.role!.roleArn,
      description:
        "Preprocessor Lambda execution role ARN. Also send-only to the Hub ingest queue; add to the Hub queue resource policy if scoping the grant to specific roles.",
    });
  }
}
