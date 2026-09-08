import * as path from "path";
import {
  Stack,
  StackProps,
  Duration,
  Size,
  CfnOutput,
  Annotations,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as sfn from "aws-cdk-lib/aws-stepfunctions";
import * as tasks from "aws-cdk-lib/aws-stepfunctions-tasks";

/**
 * ZTIE Story 2.6 (RD-029) — the CONCURRENT FORK + both-complete JOIN (Forensic
 * account, 360999005254).
 *
 * The plan (RD-002) forks a routed artifact into the two Phase-2 inspection lanes
 * but never fixed HOW. RD-029 fixes it: an AWS Step Functions STANDARD state machine
 * whose `Parallel` state fans out to the STATIC lane (2.1/2.2) and the DYNAMIC lane
 * (2.3) CONCURRENTLY, joining natively on both-branches-complete, with a per-branch
 * error `Catch` so ONE lane failing is RECORDED as that branch's result (not fatal
 * to the other). A terminal join task invokes the Story 2.6 COLLECTOR Lambda, which
 * builds ONE bounded, derived, verdict-free COLLECTED record and crosses it to the
 * Hub ingest queue (the seventh RD-013 envelope kind).
 *
 *   preprocessor --StartExecution--> [ Standard state machine ]
 *                                        |  Parallel state (CONCURRENT)
 *                                        |    ├── static branch  -> invoke static-scan lane (Catch -> recorded error)
 *                                        |    └── dynamic branch -> invoke detonation lane (Catch -> recorded error)
 *                                        |  (native join on BOTH-COMPLETE)
 *                                        └── join task -> invoke collector Lambda
 *                                                            -> sqs:SendMessage (collected record) -> Hub ingest (RD-013)
 *
 * WHY Step Functions (RD-029, over an event-driven DynamoDB-conditional join): RD-012
 * EXPLICITLY names "Step Functions execution" as the allowed EPHEMERAL per-run
 * Forensic state, so SFN adds NO durable Forensic store; it is AWS-native only; it
 * gives a native both-complete join + per-branch Catch (tolerate one-lane failure
 * without losing the other, no hand-rolled join); least-privilege; and the join is
 * idempotent under SQS at-least-once because the collected record upserts Hub-side
 * by intake_id+sha256 (RD-013/016).
 *
 * CONTAINMENT UNCHANGED: this stack only ORCHESTRATES the existing lanes — it does
 * NOT re-implement either lane and does NOT touch the detonation launch/execute
 * internals or the 2.3 artifact-fetch recipe. The dynamic lane still runs host-native
 * on the ephemeral EC2 (NO Docker, RD-001); the isolated VPC is untouched; the join
 * introduces NO durable store in Forensic and NO raw-payload crossing.
 *
 * Zero-trust: the branch inputs carry only the artifact's Forensic S3 coordinates
 * (raw body stays in Forensic, RD-009); the collector's collected record is EVIDENCE,
 * never a verdict.
 */

const FORENSIC_ACCOUNT_ID = "360999005254";

export interface ZtieOrchestrationStackProps extends StackProps {
  /** Forensic artifact bucket name (intake stack output `ArtifactBucketName`). */
  readonly artifactBucketName: string;
  /**
   * The STATIC-lane Lambda ARN (static-scan stack output `StaticScanFunctionName`
   * resolved to an ARN, or the function ARN). The static branch invokes it.
   */
  readonly staticScanFunctionArn: string;
  /**
   * The DYNAMIC-lane Lambda ARN (detonation stack output — its function ARN). The
   * dynamic branch invokes it. This stack does NOT touch its internals.
   */
  readonly detonationFunctionArn: string;
  /** Hub ingest queue URL (Hub output `IngestQueueUrl`) — the collected record crosses here. */
  readonly hubIngestQueueUrl: string;
  /** Hub ingest queue ARN (Hub output `IngestQueueArn`) — scopes the collector's send grant. */
  readonly hubIngestQueueArn: string;
}

export class ZtieOrchestrationStack extends Stack {
  /** The state machine ARN — pass to the preprocessor as ORCHESTRATION_STATE_MACHINE_ARN. */
  public readonly stateMachineArn: string;
  /** The collector Lambda's role ARN — register it as a Hub-queue sender. */
  public readonly collectorRoleArn: string;

  constructor(
    scope: Construct,
    id: string,
    props: ZtieOrchestrationStackProps,
  ) {
    super(scope, id, props);

    // Guard: the fork orchestrates the lanes that inspect/execute the artifact, so
    // it belongs in Forensic (RD-008). Warn (not hard-fail) so account-less synth
    // works.
    if (props?.env?.account && props.env.account !== FORENSIC_ACCOUNT_ID) {
      Annotations.of(this).addWarning(
        `ZTIE orchestration (fork/join) is intended for the Forensic account ` +
          `${FORENSIC_ACCOUNT_ID} (it drives the inspection lanes, RD-008); ` +
          `deploying into ${props.env.account}. Confirm this is intentional.`,
      );
    }

    // --- Imports (all in the Forensic account) -----------------------------
    const artifactBucket = s3.Bucket.fromBucketName(
      this,
      "ImportedArtifactBucket",
      props.artifactBucketName,
    );
    const staticScanFn = lambda.Function.fromFunctionArn(
      this,
      "ImportedStaticScanFn",
      props.staticScanFunctionArn,
    );
    const detonationFn = lambda.Function.fromFunctionArn(
      this,
      "ImportedDetonationFn",
      props.detonationFunctionArn,
    );

    // --- Lambda: the collector / JOIN step (PLAIN ZIP, py3.12) -------------
    // The terminal join. Pure join logic (collect.py) + a thin sqs:SendMessage seam
    // (awsio.py). It receives BOTH branch results + the fork context, builds ONE
    // bounded, verdict-free collected record, and crosses it to the Hub.
    const collectorFn = new lambda.Function(this, "CollectorJoin", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "..", "..", "lambdas", "collector"),
      ),
      // Tiny — it only joins two bounded dicts and sends one message.
      memorySize: 256,
      timeout: Duration.seconds(30),
      ephemeralStorageSize: Size.mebibytes(512),
      logRetention: logs.RetentionDays.ONE_MONTH,
      environment: {
        // The one-directional Forensic -> Hub door (same queue as the other
        // envelopes). Only the bounded collected record crosses here.
        HUB_INGEST_QUEUE_URL: props.hubIngestQueueUrl,
        // Story 2.6: the collected-record contract version (its OWN pin — a new
        // envelope kind never rides the shared CONTRACT_VERSION).
        COLLECTED_CONTRACT_VERSION: "1.0",
        LOG_LEVEL: "INFO",
      },
    });
    this.collectorRoleArn = collectorFn.role!.roleArn;

    // Least-privilege: the collector crosses to the Hub with EXACTLY sqs:SendMessage
    // on EXACTLY the one Hub ingest queue (one-directional, RD-013). No other Hub
    // access; nothing in Forensic beyond this (it reads no raw body — the per-lane
    // detail stays in Forensic behind pointers, RD-009).
    collectorFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SendCollectedRecordToHubIngestQueue",
        effect: iam.Effect.ALLOW,
        actions: ["sqs:SendMessage"],
        resources: [props.hubIngestQueueArn],
      }),
    );

    // --- Step Functions: the Parallel fork + both-complete join ------------
    // Each branch invokes its lane Lambda directly with the S3-coord job (the same
    // payload shape the lane's SQS consumer receives), and Catches a branch error
    // into a bounded recorded result so one lane failing does not fail the other or
    // the join. The Parallel state joins natively on BOTH branches complete.

    const staticInvoke = new tasks.LambdaInvoke(this, "StaticLaneInvoke", {
      lambdaFunction: staticScanFn,
      // The static branch's input is the static_job the preprocessor built.
      payload: sfn.TaskInput.fromJsonPathAt("$.static_job"),
      // Unwrap the Lambda result payload so the branch output is the lane summary.
      outputPath: "$.Payload",
      comment:
        "Static lane (2.1/2.2). Non-executing scanners; crosses its own summary. Here it is one fork branch.",
    });
    // Per-branch Catch: a lane failure becomes a bounded RECORDED result (an object
    // with an `error` marker) — the collector records it as `errored`, never a hang
    // or a drop of the other lane.
    staticInvoke.addCatch(
      new sfn.Pass(this, "StaticLaneErrored", {
        result: sfn.Result.fromObject({ error: "static lane branch failed" }),
        resultPath: "$.error",
        outputPath: "$.error",
      }),
      { errors: ["States.ALL"] },
    );

    const dynamicInvoke = new tasks.LambdaInvoke(this, "DynamicLaneInvoke", {
      lambdaFunction: detonationFn,
      payload: sfn.TaskInput.fromJsonPathAt("$.detonation_job"),
      outputPath: "$.Payload",
      comment:
        "Dynamic lane (2.3 detonation). Host-native, no Docker, isolated VPC — UNCHANGED. Here it is one fork branch.",
    });
    dynamicInvoke.addCatch(
      new sfn.Pass(this, "DynamicLaneErrored", {
        result: sfn.Result.fromObject({ error: "dynamic lane branch failed" }),
        resultPath: "$.error",
        outputPath: "$.error",
      }),
      { errors: ["States.ALL"] },
    );

    // The CONCURRENT fork: both branches run in PARALLEL for the same artifact.
    const parallel = new sfn.Parallel(this, "ForkInspectionLanes", {
      comment:
        "Story 2.6 concurrent fork: static + dynamic lanes run in PARALLEL, joined on both-complete (RD-029).",
      // Keep the fork context (intake_id/sha256/lanes_expected) available to the
      // join step alongside the two branch results.
      resultPath: "$.branch_results",
    });
    parallel.branch(staticInvoke);
    parallel.branch(dynamicInvoke);

    // The terminal JOIN task: invoke the collector with the fork context + both
    // branch results (results[0]=static, results[1]=dynamic).
    const joinInvoke = new tasks.LambdaInvoke(this, "JoinCollect", {
      lambdaFunction: collectorFn,
      payload: sfn.TaskInput.fromObject({
        "context.$": "$.context",
        "results.$": "$.branch_results",
      }),
      outputPath: "$.Payload",
      comment:
        "Terminal both-complete JOIN. Builds ONE bounded verdict-free collected record and crosses it to the Hub (7th RD-013 kind).",
    });

    const definition = parallel.next(joinInvoke);

    const stateMachine = new sfn.StateMachine(this, "InspectionOrchestration", {
      // STANDARD (RD-029) — durable, long-running (the dynamic lane launches an
      // ephemeral EC2), exactly-once execution history; NOT Express.
      stateMachineType: sfn.StateMachineType.STANDARD,
      definitionBody: sfn.DefinitionBody.fromChainable(definition),
      // Generous ceiling above the detonation lane's own budget; the dynamic branch
      // dominates the wall-clock time.
      timeout: Duration.minutes(20),
      tracingEnabled: true,
    });
    this.stateMachineArn = stateMachine.stateMachineArn;

    // --- Least-privilege wiring --------------------------------------------
    // The state machine may invoke EXACTLY the two lane Lambdas + the collector.
    // (LambdaInvoke auto-grants lambda:InvokeFunction on each referenced function to
    // the state-machine role — scoped to those three functions, nothing broader.)
    // The collector reads NO raw body; it only sends to the Hub queue (granted
    // above). The artifact bucket import is kept for parity with the lane stacks and
    // to make the Forensic containment boundary explicit; the collector is NOT
    // granted read on it (it never touches the raw body — RD-009).
    void artifactBucket;

    // --- Outputs -----------------------------------------------------------
    new CfnOutput(this, "InspectionStateMachineArn", {
      value: this.stateMachineArn,
      description:
        "Story 2.6 inspection-orchestration state machine ARN. Pass as orchestrationStateMachineArn to the intake stack (ORCHESTRATION_STATE_MACHINE_ARN on the preprocessor + a states:StartExecution grant).",
    });
    new CfnOutput(this, "CollectorFunctionName", {
      value: collectorFn.functionName,
      description:
        "Collector (join) Lambda name (Story 2.6). Tail its logs to see the joined collected record (lanes_expected/collected, both_complete, per-lane status) per intake_id.",
    });
    new CfnOutput(this, "CollectorRoleArn", {
      value: this.collectorRoleArn,
      description:
        "Collector Lambda execution role ARN. Pass as forensicCollectorRoleArn to the Hub stack so it is a send-only principal on the Hub ingest queue (tightest least-privilege).",
    });
  }
}
