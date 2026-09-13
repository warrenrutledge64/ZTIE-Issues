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
import * as s3 from "aws-cdk-lib/aws-s3";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import {
  SqsEventSource,
  DynamoEventSource,
} from "aws-cdk-lib/aws-lambda-event-sources";

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
  /**
   * ARN of the Forensic-side preprocessor (Story 1.2) Lambda role. It is the
   * SECOND one-directional sender on this queue (it emits the derived
   * classification label). Granted the same `sqs:SendMessage`-only on exactly
   * this queue. Optional; if the account-root fallback is in effect (no specific
   * intake role), it is already covered and this can be omitted.
   */
  readonly forensicPreprocessorRoleArn?: string;
  /**
   * ARN of the Forensic-side static-scan (Story 2.1) Lambda role. It is the THIRD
   * one-directional sender on this queue (it emits the derived static-scan
   * summary — the fifth envelope kind). Granted the same `sqs:SendMessage`-only on
   * exactly this queue. Optional; if the account-root fallback is in effect (no
   * specific sender roles), it is already covered and this can be omitted.
   */
  readonly forensicStaticScanRoleArn?: string;
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
      // OD-003: `pointInTimeRecovery` is deprecated in favour of the structured
      // `pointInTimeRecoverySpecification`. Same behaviour (PITR enabled), current API.
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: true,
      },
      removalPolicy: RemovalPolicy.RETAIN,
      // Story 3.1 (RD-033): a DynamoDB stream feeds the Hub-side combined-event
      // normalizer. Every time the ingest validator applies a per-lane derived
      // input (static_scan / dynamic_run / sanitized) to a tracking item, the
      // normalizer re-derives the combined event from whatever inputs have landed
      // so far. NEW_AND_OLD_IMAGES so the normalizer sees the current item; the
      // stream stays Hub-internal (no Forensic access).
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
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

    // Cross-account, least-privilege, ONE-DIRECTIONAL door. The Forensic sender
    // principals may ONLY SendMessage to THIS queue. Nothing else in the Hub is
    // reachable from Forensic. There are three senders in Forensic: the intake
    // Lambda (RECEIVED envelope, 1.1R), the preprocessor Lambda (classification /
    // routing / safe-reject envelopes, 1.2–1.4), and the static-scan Lambda
    // (static-scan summary, 2.1). If specific role ARNs are supplied, grant each
    // explicitly; otherwise fall back to the Forensic account root (still
    // one-directional and single-action, but coarser) with a synth-time warning.
    const senderRoleArns = [
      props?.forensicIntakeRoleArn,
      props?.forensicPreprocessorRoleArn,
      props?.forensicStaticScanRoleArn,
    ].filter((a): a is string => Boolean(a));

    const senderPrincipals: iam.IPrincipal[] =
      senderRoleArns.length > 0
        ? senderRoleArns.map((arn) => new iam.ArnPrincipal(arn))
        : [new iam.AccountPrincipal(FORENSIC_ACCOUNT_ID)];

    if (senderRoleArns.length === 0) {
      Annotations.of(this).addWarning(
        `No Forensic sender role ARNs provided; granting sqs:SendMessage to the ` +
          `Forensic account root (${FORENSIC_ACCOUNT_ID}) instead of specific ` +
          `roles. Prefer passing forensicIntakeRoleArn + ` +
          `forensicPreprocessorRoleArn + forensicStaticScanRoleArn for tightest ` +
          `least-privilege (RD-013).`,
      );
    }

    ingestQueue.addToResourcePolicy(
      new iam.PolicyStatement({
        sid: "AllowForensicSendOnly",
        effect: iam.Effect.ALLOW,
        principals: senderPrincipals,
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
    // OD-003: explicit LogGroup replaces the deprecated `logRetention` prop.
    const validatorLogGroup = new logs.LogGroup(
      this,
      "IngestValidatorLogGroup",
      {
        retention: logs.RetentionDays.ONE_MONTH,
        removalPolicy: RemovalPolicy.DESTROY,
      },
    );
    const validatorFn = new lambda.Function(this, "IngestValidator", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(hubIngestDir, {
        bundling: {
          // MUST bundle in the Lambda Python 3.12 image (not local pip). A
          // transitive dep of jsonschema — `rpds-py` — ships a COMPILED native
          // extension (`rpds.rpds`). Building it with local pip on CloudShell
          // (Python 3.13 / different platform) produces a binary the Lambda
          // Python 3.12 runtime cannot import ("No module named 'rpds.rpds'").
          // Docker bundling in the matching runtime image produces the correct
          // manylinux binary. NO `local` fallback here for that reason.
          image: DockerImage.fromRegistry("public.ecr.aws/lambda/python:3.12"),
          // Override the Lambda base image's entrypoint (it expects a handler
          // name as arg1); we just want a shell to pip-install into /asset-output.
          entrypoint: ["bash", "-c"],
          command: [
            [
              // Force platform-correct prebuilt wheels for the Lambda runtime.
              "pip install --no-cache-dir " +
                "--platform manylinux2014_x86_64 " +
                "--implementation cp --python-version 3.12 " +
                "--only-binary=:all: --upgrade " +
                "-r requirements.txt -t /asset-output",
              "cp -r . /asset-output",
            ].join(" && "),
          ],
        },
      }),
      timeout: Duration.seconds(30),
      memorySize: 256,
      logGroup: validatorLogGroup,
      environment: {
        TRACKING_TABLE: trackingTable.tableName,
        QUARANTINE_BUCKET: quarantineBucket.bucketName,
        CONTRACT_VERSION: "1.0",
        // Story 2.4: the behavioral-telemetry envelope (the EIGHTH kind) pins its
        // OWN version so it validates independently of the shared CONTRACT_VERSION
        // and the other per-kind pins. The handler defaults this to "1.0" too; set
        // it explicitly here so a Hub redeploy carries the pin alongside the bundled
        // behavior.contract.v1.json (the deploy-gap lesson — ship the contract).
        BEHAVIOR_CONTRACT_VERSION: "1.0",
        // Story 2.5: the sanitized-telemetry envelope (the NINTH kind) pins its OWN
        // version so it validates independently of the shared CONTRACT_VERSION and
        // the other per-kind pins. Set explicitly here so a Hub redeploy carries the
        // pin alongside the bundled sanitized-telemetry.contract.v1.json (the
        // deploy-gap lesson — ship the contract or the crossed record fail-closed
        // QUARANTINES).
        SANITIZED_TELEMETRY_CONTRACT_VERSION: "1.0",
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
    // (upsert for intake, conditional update for the Story 1.2 classification
    // label) and quarantine objects. Story 1.2 also needs READ on the table: when
    // a classification's conditional update fails, the validator does a single
    // GetItem to disambiguate "record not present yet" (an ordering race -> retry)
    // from "sha256 mismatch" (an integrity violation -> quarantine). It does NOT
    // read the Forensic S3 body (it cannot and must not).
    trackingTable.grantReadWriteData(validatorFn);
    quarantineBucket.grantPut(validatorFn);

    // --- Lambda: the Story 3.1 Hub-side combined-event normalizer (RD-033) ----
    // The FIRST Phase-3 component. It is triggered by the tracking table's stream:
    // every time the ingest validator applies a per-lane derived input to an item,
    // this re-reads the CURRENT item and normalizes the three inputs (static_scan /
    // dynamic_run / sanitized) into ONE bounded, verdict-free combined-event record
    // written back onto the SAME item (field `combined_event`). It is Hub-SIDE only
    // — it reads already-Hub derived data and never touches Forensic (RD-009) and
    // never crosses the RD-013 gate (the combined event never leaves the Hub). Its
    // normalization logic is PURE stdlib (combine.py), so — unlike the validator —
    // it has NO third-party runtime dep and needs NO Docker bundling; the plain asset
    // (handler + combine + awsio + the bundled combined-event contract) suffices.
    const hubNormalizeDir = path.join(
      __dirname,
      "..",
      "..",
      "lambdas",
      "hub_normalize",
    );
    // OD-003: explicit LogGroup replaces the deprecated `logRetention` prop.
    const normalizerLogGroup = new logs.LogGroup(
      this,
      "CombinedEventNormalizerLogGroup",
      {
        retention: logs.RetentionDays.ONE_MONTH,
        removalPolicy: RemovalPolicy.DESTROY,
      },
    );
    const normalizerFn = new lambda.Function(this, "CombinedEventNormalizer", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(hubNormalizeDir),
      timeout: Duration.seconds(30),
      memorySize: 256,
      logGroup: normalizerLogGroup,
      environment: {
        TRACKING_TABLE: trackingTable.tableName,
        // Story 3.1: the combined-event record pins its OWN version so it evolves
        // independently of the shared CONTRACT_VERSION and every crossing kind's
        // pin. Set explicitly here so a Hub redeploy carries the pin alongside the
        // bundled combined-event.contract.v1.json.
        COMBINED_EVENT_CONTRACT_VERSION: "1.0",
        LOG_LEVEL: "INFO",
      },
    });

    // The normalizer reads the tracking item and writes the combined event back
    // onto it (integrity-bound conditional update). Read + write on the table only.
    trackingTable.grantReadWriteData(normalizerFn);

    // Trigger the normalizer from the tracking table's stream. It re-derives the
    // combined event whenever an item changes; its own write is idempotent (it only
    // writes when the derived combined event actually changed) so the stream does
    // not loop. reportBatchItemFailures so only a failed item is retried.
    normalizerFn.addEventSource(
      new DynamoEventSource(trackingTable, {
        startingPosition: lambda.StartingPosition.LATEST,
        batchSize: 10,
        retryAttempts: 3,
        reportBatchItemFailures: true,
      }),
    );

    // --- Lambda: the Story 3.2 Hub-side Nova Pro correlation engine (RD-035) --
    // The AI-correlation CORE of Phase 3. It is triggered by the SAME tracking-table
    // stream as the 3.1 normalizer: whenever an item changes, it re-reads the CURRENT
    // item and — IF the 3.1 `combined_event` is ready to correlate AND has not already
    // been correlated for its current content (a fingerprint guard, to avoid a Nova
    // Pro call storm / stream loop) — hands the ONE bounded combined event to Amazon
    // Nova Pro (RD-003, via bedrock-runtime, with real exponential-backoff retry) and
    // records a bounded, verdict-free correlation RESULT (`correlation.contract.v1`)
    // back onto the SAME item (field `correlation_result` + flattened
    // `correlation_status`). It is Hub-SIDE only — it reasons over already-Hub derived
    // data (the combined event) and never touches Forensic (RD-009) and never crosses
    // the RD-013 gate (the correlation result never leaves the Hub). Its prompt-build
    // + response-parse logic is PURE stdlib (correlate.py), so — like the normalizer —
    // it has NO third-party runtime dep and needs NO Docker bundling; the plain asset
    // (handler + correlate + awsio + the bundled correlation contract) suffices.
    //
    // Nova Pro model id: Nova Pro on-demand is invoked through a region-prefixed
    // cross-region inference profile (default `us.amazon.nova-pro-v1:0`), overridable
    // via the `novaModelId` context so the exact profile/region can be pinned without
    // a code change. The `bedrock:InvokeModel` grant is scoped to BOTH the inference
    // profile ARN and the underlying foundation-model ARN(s) it routes to (a
    // cross-region profile fans out to the model in each region in its geography), so
    // the call is authorized without opening `bedrock:InvokeModel` on `*`.
    const novaModelId =
      (this.node.tryGetContext("novaModelId") as string | undefined) ??
      "us.amazon.nova-pro-v1:0";
    // Correlate only once the combined event is COMPLETE (all three inputs landed)
    // so we do not spend a Nova Pro call on every partial re-derive. Set context
    // `correlateOnlyWhenComplete=0` to correlate as soon as any signal is present.
    const correlateOnlyWhenComplete =
      (this.node.tryGetContext("correlateOnlyWhenComplete") as
        string | undefined) ?? "1";
    // Strip a leading region/geo prefix (e.g. "us.") to recover the bare
    // foundation-model id for the model-ARN grant.
    const bareNovaModelId = novaModelId.replace(/^[a-z]{2,3}\./, "");
    const bedrockModelResources = [
      // The inference profile itself (in this Hub account + region).
      `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/${novaModelId}`,
      // The foundation model in this region (what a same-region invoke resolves to).
      `arn:aws:bedrock:${this.region}::foundation-model/${bareNovaModelId}`,
      // A cross-region "us." profile can route to the model in any US region; grant
      // the foundation-model ARN region-wildcarded so the profile's fan-out is
      // authorized. Still scoped to EXACTLY this one Nova Pro model (never `*`).
      `arn:aws:bedrock:*::foundation-model/${bareNovaModelId}`,
    ];

    const hubCorrelateDir = path.join(
      __dirname,
      "..",
      "..",
      "lambdas",
      "hub_correlate",
    );
    // OD-003: explicit LogGroup replaces the deprecated `logRetention` prop.
    const correlatorLogGroup = new logs.LogGroup(
      this,
      "NovaCorrelatorLogGroup",
      {
        retention: logs.RetentionDays.ONE_MONTH,
        removalPolicy: RemovalPolicy.DESTROY,
      },
    );
    const correlatorFn = new lambda.Function(this, "NovaCorrelator", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(hubCorrelateDir),
      // A real Nova Pro call + up to NOVA_MAX_ATTEMPTS exponential backoffs can take
      // a while; give it generous headroom (still bounded).
      timeout: Duration.seconds(120),
      memorySize: 256,
      logGroup: correlatorLogGroup,
      environment: {
        TRACKING_TABLE: trackingTable.tableName,
        // Story 3.2: the correlation-result record pins its OWN version so it evolves
        // independently of the shared CONTRACT_VERSION and every crossing kind's pin.
        // Set explicitly here so a Hub redeploy carries the pin alongside the bundled
        // correlation.contract.v1.json (the deploy-gap lesson — ship the contract).
        CORRELATION_CONTRACT_VERSION: "1.0",
        // The Nova Pro model / inference-profile id (RD-003). Kept in lockstep with
        // the IAM grant above.
        NOVA_MODEL_ID: novaModelId,
        // Bounded exponential-backoff retry budget (RD-003).
        NOVA_MAX_ATTEMPTS: "5",
        // Gate the Nova Pro call on combined-event completeness (see the context
        // read above): "1" = only when all three inputs landed; "0" = any signal.
        CORRELATE_ONLY_WHEN_COMPLETE: correlateOnlyWhenComplete,
        LOG_LEVEL: "INFO",
      },
    });

    // The correlator reads the tracking item and writes the correlation result back
    // onto it (integrity-bound conditional update). Read + write on the table only.
    trackingTable.grantReadWriteData(correlatorFn);

    // Least-privilege Bedrock: invoke EXACTLY the Nova Pro model / inference profile
    // (RD-003), never `bedrock:InvokeModel` on `*`.
    correlatorFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "InvokeNovaProOnly",
        effect: iam.Effect.ALLOW,
        actions: ["bedrock:InvokeModel"],
        resources: bedrockModelResources,
      }),
    );

    // Trigger the correlator from the tracking table's stream. It correlates once per
    // settled combined event (fingerprint-guarded), so its own write (which does not
    // change the combined event) does not loop the stream. reportBatchItemFailures so
    // only a failed item is retried.
    correlatorFn.addEventSource(
      new DynamoEventSource(trackingTable, {
        startingPosition: lambda.StartingPosition.LATEST,
        batchSize: 10,
        retryAttempts: 3,
        reportBatchItemFailures: true,
      }),
    );

    // --- Lambda: the Story 3.3 Hub-side three-score risk scorer (RD-038, reworked) --
    // The false-positive-elimination + gap step of Phase 3. It is triggered by the
    // SAME tracking-table stream as the 3.1 normalizer + 3.2 correlator: whenever an
    // item changes, it re-reads the CURRENT item and — IF the 3.2 `correlation_result`
    // is present AND has not already been scored for its current content (a
    // fingerprint guard, to avoid re-work / a stream loop) — makes THREE SEPARATE,
    // evidence-scoped Amazon Nova Pro calls and records a bounded, verdict-free
    // scoring RESULT (`scoring.contract.v1`) back onto the SAME item (field
    // `scoring_result`).
    //
    // RD-038 (reworked; supersedes the RD-037 build): 3.3 produces THREE INDEPENDENT
    // 0-100 risk scores — a STATIC score (Nova Pro over ONLY the static lane's derived
    // evidence), a DYNAMIC score (Nova Pro over ONLY the dynamic lane's derived
    // evidence, a peer of static), and a COMBINED score (Nova Pro over BOTH lanes'
    // derived evidence together, its own assessment — NOT a formula over the two).
    // All three share ONE 0-100 rubric so they are comparable (higher = riskier). So
    // — UNLIKE the RD-037 build (which had NO model call) and LIKE the 3.2 correlator
    // — this Lambda DOES call Bedrock (three times) and IS granted a scoped
    // `bedrock:InvokeModel` (reusing the same Nova-Pro-only ARN scoping as the
    // correlator, never `*`). It is Hub-SIDE only — it reasons over already-Hub
    // DERIVED evidence (never the raw payload / trace — RD-009) and never crosses the
    // RD-013 gate (the scoring result never leaves the Hub). Its scoring logic is PURE
    // stdlib (score.py), so it needs NO Docker bundling; the plain asset (handler +
    // score + awsio + the bundled scoring contract) suffices. EVIDENCE only — the
    // three scores are risk metrics, never a verdict (the verdict is human-gated, 3.5).
    const hubSynthesizeDir = path.join(
      __dirname,
      "..",
      "..",
      "lambdas",
      "hub_synthesize",
    );
    // Score only once the combined event is COMPLETE (all inputs landed) so we do not
    // spend three Nova Pro calls on every partial re-derive. Set context
    // `scoreOnlyWhenComplete=0` to score as soon as any lane evidence is present.
    const scoreOnlyWhenComplete =
      (this.node.tryGetContext("scoreOnlyWhenComplete") as
        string | undefined) ?? "1";
    // OD-003: explicit LogGroup replaces the deprecated `logRetention` prop.
    const synthesizerLogGroup = new logs.LogGroup(
      this,
      "SynthesisSynthesizerLogGroup",
      {
        retention: logs.RetentionDays.ONE_MONTH,
        removalPolicy: RemovalPolicy.DESTROY,
      },
    );
    const synthesizerFn = new lambda.Function(this, "SynthesisSynthesizer", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(hubSynthesizeDir),
      // Three real Nova Pro calls + up to NOVA_MAX_ATTEMPTS backoffs each can take a
      // while; give generous headroom (still bounded).
      timeout: Duration.seconds(180),
      memorySize: 256,
      logGroup: synthesizerLogGroup,
      environment: {
        TRACKING_TABLE: trackingTable.tableName,
        // Story 3.3 (RD-038): the scoring-result record pins its OWN version so it
        // evolves independently of the shared CONTRACT_VERSION and every crossing
        // kind's pin. Set explicitly so a Hub redeploy carries the pin alongside the
        // bundled scoring.contract.v1.json (the deploy-gap lesson — ship the contract).
        SCORING_CONTRACT_VERSION: "1.0",
        // The Nova Pro model / inference-profile id (RD-003), kept in lockstep with
        // the IAM grant below (same value the correlator uses).
        NOVA_MODEL_ID: novaModelId,
        // Bounded exponential-backoff retry budget (RD-003), per score call.
        NOVA_MAX_ATTEMPTS: "5",
        // Gate the three calls on combined-event completeness: "1" = only when all
        // inputs landed; "0" = as soon as any lane evidence is present.
        SCORE_ONLY_WHEN_COMPLETE: scoreOnlyWhenComplete,
        LOG_LEVEL: "INFO",
      },
    });

    // The scorer reads the tracking item and writes the scoring result back onto it
    // (integrity-bound conditional update). Read + write on the table only.
    trackingTable.grantReadWriteData(synthesizerFn);

    // Least-privilege Bedrock (RD-038): invoke EXACTLY the Nova Pro model / inference
    // profile (RD-003), never `bedrock:InvokeModel` on `*`. Same scoping as the 3.2
    // correlator (reusing `bedrockModelResources` defined above).
    synthesizerFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "InvokeNovaProForScoring",
        effect: iam.Effect.ALLOW,
        actions: ["bedrock:InvokeModel"],
        resources: bedrockModelResources,
      }),
    );

    // Trigger the scorer from the tracking table's stream. It scores once per settled
    // evidence (fingerprint-guarded), so its own write (which does not change the
    // combined event) does not loop the stream. reportBatchItemFailures so only a
    // failed item is retried.
    synthesizerFn.addEventSource(
      new DynamoEventSource(trackingTable, {
        startingPosition: lambda.StartingPosition.LATEST,
        batchSize: 10,
        retryAttempts: 3,
        reportBatchItemFailures: true,
      }),
    );

    // --- Lambda: the Story 3.4 Hub-side findings + prioritized-remediations step (RD-039) --
    // The findings + remediations step of Phase 3, and the LAST derived-record step
    // before the 3.5 verdict. It is triggered by the SAME tracking-table stream as the
    // 3.1 normalizer + 3.2 correlator + 3.3 scorer: whenever an item changes, it
    // re-reads the CURRENT item and — IF the 3.3 `scoring_result` is present AND has not
    // already been assessed for its current content (a fingerprint guard over the scores
    // + the correlation findings, to avoid re-work / a stream loop) — builds a bounded,
    // verdict-free `remediation_result` (`remediation.contract.v1`) back onto the SAME
    // item (field `remediation_result`). It turns the three 3.3 risk scores + the 3.2
    // correlation findings into DETAILED FINDINGS (the correlation findings surfaced +
    // the migrated candidate-false-positive list + the gap list) and a PRIORITIZED
    // REMEDIATION list ranked highest-risk-first.
    //
    // RD-039 CONTRACT-FIRST decision: this is PURE Hub-side post-processing — it makes
    // NO model call. Its inputs are ALREADY fully structured (three 0-100 scores +
    // categorized findings on the Hub item), so building the findings view + ranking the
    // remediations is deterministic; a Nova Pro call would only add cost /
    // non-determinism / verdict-risk for no gain. So — UNLIKE the 3.2 correlator + the
    // 3.3 scorer — this Lambda has NO Bedrock client and NO Bedrock grant. It is
    // Hub-SIDE only: it reasons over already-Hub DERIVED evidence (never the raw payload
    // / trace — RD-009) and never crosses the RD-013 gate (the remediation result never
    // leaves the Hub). Its assessment logic is PURE stdlib (remediate.py), so it needs NO
    // Docker bundling; the plain asset (handler + remediate + awsio + the bundled
    // remediation contract) suffices. EVIDENCE + a to-do list, never a verdict — a
    // remediation is "fix X", never "reject the artifact" (the verdict is human-gated,
    // Story 3.5).
    const hubRemediateDir = path.join(
      __dirname,
      "..",
      "..",
      "lambdas",
      "hub_remediate",
    );
    // OD-003: explicit LogGroup replaces the deprecated `logRetention` prop.
    const remediateLogGroup = new logs.LogGroup(
      this,
      "FindingsRemediationLogGroup",
      {
        retention: logs.RetentionDays.ONE_MONTH,
        removalPolicy: RemovalPolicy.DESTROY,
      },
    );
    const remediateFn = new lambda.Function(this, "FindingsRemediation", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(hubRemediateDir),
      // PURE post-processing (no model call), so the default headroom is plenty.
      timeout: Duration.seconds(30),
      memorySize: 256,
      logGroup: remediateLogGroup,
      environment: {
        TRACKING_TABLE: trackingTable.tableName,
        // Story 3.4 (RD-039): the remediation-result record pins its OWN version so it
        // evolves independently of the shared CONTRACT_VERSION and every crossing kind's
        // pin. Set explicitly so a Hub redeploy carries the pin alongside the bundled
        // remediation.contract.v1.json (the deploy-gap lesson — ship the contract).
        REMEDIATION_CONTRACT_VERSION: "1.0",
        LOG_LEVEL: "INFO",
      },
    });

    // The 3.4 step reads the tracking item and writes the remediation result back onto
    // it (integrity-bound conditional update). Read + write on the table only. NO
    // Bedrock grant (RD-039: PURE — no model call).
    trackingTable.grantReadWriteData(remediateFn);

    // Trigger the 3.4 step from the tracking table's stream. It assesses once per
    // settled evidence (fingerprint-guarded over the scores + findings), so its own
    // write (which changes neither) does not loop the stream. reportBatchItemFailures so
    // only a failed item is retried.
    remediateFn.addEventSource(
      new DynamoEventSource(trackingTable, {
        startingPosition: lambda.StartingPosition.LATEST,
        batchSize: 10,
        retryAttempts: 3,
        reportBatchItemFailures: true,
      }),
    );

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
    new CfnOutput(this, "CombinedEventNormalizerName", {
      value: normalizerFn.functionName,
      description:
        "Story 3.1 Hub-side combined-event normalizer Lambda (DynamoDB-Streams-triggered).",
    });
    new CfnOutput(this, "NovaCorrelatorName", {
      value: correlatorFn.functionName,
      description:
        "Story 3.2 Hub-side Nova Pro correlation engine Lambda (DynamoDB-Streams-triggered).",
    });
    new CfnOutput(this, "SynthesisSynthesizerName", {
      value: synthesizerFn.functionName,
      description:
        "Story 3.3 Hub-side three-score risk scorer Lambda (RD-038; DynamoDB-Streams-triggered; three scoped Nova Pro calls; scoped bedrock:InvokeModel).",
    });
    new CfnOutput(this, "FindingsRemediationName", {
      value: remediateFn.functionName,
      description:
        "Story 3.4 Hub-side findings + prioritized-remediations Lambda (RD-039; DynamoDB-Streams-triggered; PURE, no Bedrock).",
    });
    new CfnOutput(this, "NovaModelId", {
      value: novaModelId,
      description:
        "Story 3.2 Amazon Nova Pro model / inference-profile id the correlator invokes (RD-003).",
    });
  }
}
