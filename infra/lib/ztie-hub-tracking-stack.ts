import * as path from "path";
import { execSync } from "child_process";
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
import * as s3 from "aws-cdk-lib/aws-s3";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import { SqsEventSource } from "aws-cdk-lib/aws-lambda-event-sources";

/**
 * ZTIE Story 1.1R — Hub-side durable tracking + the Forensic -> Hub data-contract
 * gate (RD-012 / RD-013).
 *
 * This stack deploys into the **Hub** account (Pipeline-Hub, 641628980935) — the
 * brains / control plane. It owns the DURABLE record that RD-012 says must NOT
 * live in the disposable Forensic blast zone, and it owns the single validating
 * door (RD-013) through which anything from Forensic must pass.
 *
 *   Forensic intake Lambda  --sqs:SendMessage-->  [Hub ingest queue]
 *        (least-privilege, one-directional)             |
 *                                                        v
 *                                            [Hub validator Lambda]
 *                                        jsonschema (fail-closed)
 *                                          |                      |
 *                                    PASS  v                 FAIL v
 *                            [Hub tracking DynamoDB]   [Hub quarantine S3]
 *                              (upsert by intake_id)   (+ ingest DLQ)
 *
 * The Forensic principal is granted EXACTLY `sqs:SendMessage` on EXACTLY this one
 * queue (via the queue resource policy). It has NO permission on the tracking
 * table, the quarantine bucket, or anything else in the Hub. The verdict
 * (PASS/FAIL/INCONCLUSIVE) is decided Hub-side by the human gate (Phase 4) and is
 * never imported from crossed data.
 */

const HUB_ACCOUNT_ID = "641628980935";
const FORENSIC_ACCOUNT_ID = "360999005254";

export interface ZtieHubTrackingStackProps extends StackProps {
  /**
   * ARN of the Forensic-side IAM role that the intake Lambda assumes. Only this
   * principal is granted `sqs:SendMessage` on the ingest queue. If omitted, the
   * grant falls back to the whole Forensic account root (still one-directional
   * and single-action, but coarser) and a synth-time warning is emitted.
   */
  readonly forensicIntakeRoleArn?: string;
}

export class ZtieHubTrackingStack extends Stack {
  /** Ingest queue URL — handed to the Forensic stack so intake can SendMessage. */
  public readonly ingestQueueArn: string;

  constructor(scope: Construct, id: string, props?: ZtieHubTrackingStackProps) {
    super(scope, id, props);

    // Guard: this is the control plane. Warn loudly if it is not the Hub account.
    if (props?.env?.account && props.env.account !== HUB_ACCOUNT_ID) {
      Annotations.of(this).addWarning(
        `ZTIE Hub tracking is intended for the Hub account ${HUB_ACCOUNT_ID} ` +
          `(brains / control plane, RD-008); deploying into ${props.env.account}. ` +
          `The durable tracking record must live in the Hub, out of the blast zone ` +
          `(RD-012). Confirm this is intentional.`,
      );
    }

    // --- DynamoDB: the DURABLE authoritative tracking record (RD-012) --------
    // Lives in the Hub so it survives Forensic blast-zone teardown and is the
    // audit trail. Keyed by intake_id; the validator upserts by this key.
    const trackingTable = new dynamodb.Table(this, "TrackingTable", {
      partitionKey: { name: "intake_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
      removalPolicy: RemovalPolicy.RETAIN,
    });

    // List tracking records by status (e.g. all RECEIVED) without a full scan.
    trackingTable.addGlobalSecondaryIndex({
      indexName: "status-received_at-index",
      partitionKey: { name: "status", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "received_at", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // --- S3: quarantine for records that FAIL the data contract --------------
    // Fail-closed: a non-conforming envelope is written here (never to the live
    // table) with the rejection reason, for audit. Encrypted, block-public.
    const quarantineBucket = new s3.Bucket(this, "QuarantineBucket", {
      encryption: s3.BucketEncryption.KMS_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      versioned: true,
      removalPolicy: RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          // Quarantined material is for audit/triage; expire after a bounded window.
          expiration: Duration.days(180),
          noncurrentVersionExpiration: Duration.days(30),
          abortIncompleteMultipartUploadAfter: Duration.days(7),
        },
      ],
    });

    // --- SQS: the one-directional Forensic -> Hub door + its DLQ -------------
    const ingestDlq = new sqs.Queue(this, "IngestDlq", {
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      enforceSSL: true,
      retentionPeriod: Duration.days(14),
    });

    const ingestQueue = new sqs.Queue(this, "IngestQueue", {
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      enforceSSL: true,
      // Give the validator room to run; must be >= the Lambda timeout.
      visibilityTimeout: Duration.seconds(60),
      retentionPeriod: Duration.days(4),
      deadLetterQueue: {
        queue: ingestDlq,
        // A message the validator cannot even process (not a contract failure —
        // that is handled in-band via quarantine) redrives to the DLQ.
        maxReceiveCount: 5,
      },
    });
    this.ingestQueueArn = ingestQueue.queueArn;

    // Cross-account, least-privilege, ONE-DIRECTIONAL door. The Forensic intake
    // principal may ONLY SendMessage to THIS queue. Nothing else in the Hub is
    // reachable from Forensic.
    const forensicPrincipal: iam.IPrincipal = props?.forensicIntakeRoleArn
      ? new iam.ArnPrincipal(props.forensicIntakeRoleArn)
      : new iam.AccountPrincipal(FORENSIC_ACCOUNT_ID);

    if (!props?.forensicIntakeRoleArn) {
      Annotations.of(this).addWarning(
        `No forensicIntakeRoleArn provided; granting sqs:SendMessage to the ` +
          `Forensic account root (${FORENSIC_ACCOUNT_ID}) instead of a specific ` +
          `role. Prefer passing the exact intake role ARN for tightest ` +
          `least-privilege (RD-013).`,
      );
    }

    ingestQueue.addToResourcePolicy(
      new iam.PolicyStatement({
        sid: "AllowForensicIntakeSendOnly",
        effect: iam.Effect.ALLOW,
        principals: [forensicPrincipal],
        actions: ["sqs:SendMessage"],
        resources: [ingestQueue.queueArn],
      }),
    );

    // --- Lambda: the Hub-owned validating ingestion gate ---------------------
    // The validator depends on `jsonschema`, which is NOT in the Lambda runtime,
    // so the asset is BUNDLED: dependencies are pip-installed into the package
    // alongside the handler + the bundled contract schema. Local bundling is used
    // (works in CloudShell without Docker); if a local Python toolchain is
    // unavailable, CDK falls back to the Docker image below.
    const hubIngestDir = path.join(
      __dirname,
      "..",
      "..",
      "lambdas",
      "hub_ingest",
    );
    const validatorFn = new lambda.Function(this, "IngestValidator", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(hubIngestDir, {
        bundling: {
          image: DockerImage.fromRegistry("public.ecr.aws/lambda/python:3.12"),
          // Override the Lambda base image's entrypoint (it expects a handler
          // name as arg1); we just want a shell to pip-install into /asset-output.
          entrypoint: ["bash", "-c"],
          command: [
            [
              "pip install --no-cache-dir -r requirements.txt -t /asset-output",
              "cp -r . /asset-output",
            ].join(" && "),
          ],
          local: {
            tryBundle(outputDir: string): boolean {
              try {
                // Route pip's build/temp onto the same (roomy) filesystem as the
                // output dir. CloudShell's /tmp is tiny, which causes ENOSPC and
                // "Invalid cross-device link" during pip's move step. --no-cache-dir
                // avoids filling the home cache too.
                const env = {
                  ...process.env,
                  TMPDIR: outputDir,
                  PIP_NO_CACHE_DIR: "1",
                };
                execSync(
                  [
                    `python3 -m pip install --no-cache-dir ` +
                      `-r "${path.join(hubIngestDir, "requirements.txt")}" ` +
                      `-t "${outputDir}"`,
                    `cp -r "${hubIngestDir}/." "${outputDir}"`,
                  ].join(" && "),
                  { stdio: "inherit", env },
                );
                return true;
              } catch {
                // Fall back to Docker bundling.
                return false;
              }
            },
          },
        },
      }),
      timeout: Duration.seconds(30),
      memorySize: 256,
      logRetention: logs.RetentionDays.ONE_MONTH,
      environment: {
        TRACKING_TABLE: trackingTable.tableName,
        QUARANTINE_BUCKET: quarantineBucket.bucketName,
        CONTRACT_VERSION: "1.0",
        LOG_LEVEL: "INFO",
      },
    });

    // The validator reads from the ingest queue.
    validatorFn.addEventSource(
      new SqsEventSource(ingestQueue, {
        batchSize: 10,
        // Surface per-message failures so only failed messages are retried/DLQ'd
        // rather than the whole batch.
        reportBatchItemFailures: true,
      }),
    );

    // Least-privilege on the Hub side: the validator may write tracking records
    // (upsert) and quarantine objects — nothing more. It does NOT read the
    // Forensic S3 body (it cannot and must not).
    trackingTable.grantWriteData(validatorFn);
    quarantineBucket.grantPut(validatorFn);

    // --- Outputs (used by the two-account deploy + live-validation handoff) --
    new CfnOutput(this, "IngestQueueUrl", {
      value: ingestQueue.queueUrl,
      description:
        "Hub ingest SQS queue URL. Set as HUB_INGEST_QUEUE_URL on the Forensic intake Lambda.",
    });
    new CfnOutput(this, "IngestQueueArn", {
      value: ingestQueue.queueArn,
      description:
        "Hub ingest SQS queue ARN (for the Forensic-side send grant).",
    });
    new CfnOutput(this, "IngestDlqUrl", {
      value: ingestDlq.queueUrl,
      description: "Hub ingest DLQ URL (unprocessable messages).",
    });
    new CfnOutput(this, "TrackingTableName", {
      value: trackingTable.tableName,
      description:
        "Hub durable tracking DynamoDB table (authoritative record).",
    });
    new CfnOutput(this, "QuarantineBucketName", {
      value: quarantineBucket.bucketName,
      description: "Hub quarantine S3 bucket (contract-failing records).",
    });
  }
}
