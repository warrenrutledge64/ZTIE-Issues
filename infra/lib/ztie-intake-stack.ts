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
      description: "Forensic S3 bucket holding raw intake artifact bodies.",
    });
    new CfnOutput(this, "IntakeHandlerRoleArn", {
      value: intakeFn.role!.roleArn,
      description:
        "Intake Lambda execution role ARN. Pass as forensicIntakeRoleArn to the Hub stack for tightest send-only grant.",
    });
  }
}
