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
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as apigateway from "aws-cdk-lib/aws-apigateway";

/**
 * ZTIE Story 1.1 — Intake gateway.
 *
 * POST /intake (API Gateway REST, IAM/SigV4 auth) -> intake Lambda (Python 3.12)
 * -> artifact body persisted to an encrypted, versioned, block-public S3 bucket
 * and a queryable intake record written to an on-demand encrypted DynamoDB table
 * with status=RECEIVED.
 *
 * Zero-trust: nothing here classifies, marks safe, or forwards an artifact.
 * IAM auth gates who may submit; the record starts life as RECEIVED.
 *
 * Topology (RD-008/009): this stack deploys into the Forensic account
 * (360999005254). Both the raw artifact body (S3) and the intake record
 * (DynamoDB) stay in Forensic — the blast zone. Surfacing DERIVED metadata to
 * the Hub (Pipeline-Hub, 641628980935) for the dashboard is a separate, later
 * story (one-directional Forensic -> Hub push, least-privilege); it is NOT done
 * here and no raw payload ever crosses to the Hub.
 */

/**
 * Forensic account (360999005254) — ZTIE self-contained + ultimate blast-radius
 * containment (RD-008/009). Intake, the raw artifact body (S3), and the intake
 * record (DynamoDB) all live HERE. The Hub (Pipeline-Hub, 641628980935) never
 * receives or stores the raw payload; only DERIVED metadata is surfaced to the
 * Hub, which is a separate, later story (Forensic -> Hub push, least-privilege).
 */
const FORENSIC_ACCOUNT_ID = "360999005254";

export class ZtieIntakeStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
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

    // --- DynamoDB: queryable intake record ---------------------------------
    const intakeTable = new dynamodb.Table(this, "IntakeTable", {
      partitionKey: { name: "intake_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
      removalPolicy: RemovalPolicy.RETAIN,
    });

    // GSI so downstream stories (the preprocessor, dashboards) can list intake
    // records by status (e.g. all RECEIVED awaiting classification) without a
    // full-table scan.
    intakeTable.addGlobalSecondaryIndex({
      indexName: "status-received_at-index",
      partitionKey: { name: "status", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "received_at", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

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
        INTAKE_TABLE: intakeTable.tableName,
        LOG_LEVEL: "INFO",
        // ~6 MB decoded, safely under API Gateway's ~10 MB request cap.
        MAX_ARTIFACT_BYTES: String(6 * 1024 * 1024),
      },
    });

    // Least-privilege: write artifact bodies + intake records only.
    artifactBucket.grantPut(intakeFn);
    intakeTable.grantWriteData(intakeFn);

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
      description: "S3 bucket holding intake artifact bodies.",
    });
    new CfnOutput(this, "IntakeTableName", {
      value: intakeTable.tableName,
      description: "DynamoDB table holding intake records (status=RECEIVED).",
    });
  }
}
