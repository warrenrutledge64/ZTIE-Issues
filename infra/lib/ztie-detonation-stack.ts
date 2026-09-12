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
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";
import { SqsEventSource } from "aws-cdk-lib/aws-lambda-event-sources";

/**
 * ZTIE Story 2.3 — the DYNAMIC (detonation) lane (Forensic account, 360999005254).
 *
 * The EXECUTING counterpart to the non-executing static lane (2.1/2.2). It consumes
 * the Forensic detonation work queue (produced by the intake stack's preprocessor
 * when routing names the `dynamic_detonation` lane), launches ONE ephemeral EC2 from
 * the Story 2.0 launch template via `ec2:RunInstances` (NOT CloudFormation-per-run)
 * into the isolated VPC, EXECUTES the artifact host-native via SSM (AWS-RunShellScript
 * — NO Docker, RD-001), lets the host self-terminate on the 5-min hard TTL, writes
 * the full command log to Forensic S3 under `runs/` (RD-009 — it stays in Forensic),
 * and crosses only a bounded, derived, verdict-free run OUTCOME to the Hub ingest
 * queue via the RD-013 gate (the sixth envelope kind).
 *
 *   [detonation work queue] --(consume)--> [detonation Lambda (plain zip, py3.12)]
 *        (intra-Forensic)                        |    |    |
 *              ec2:RunInstances (2.0 template) ---+    |    |
 *              ssm:SendCommand (host-native, no Docker)|    |
 *                                    write runs/ (Forensic S3, full log)
 *                                                      |
 *                                    sqs:SendMessage (run outcome) -> Hub ingest (RD-013)
 *
 * PACKAGING: a PLAIN ZIP `lambda.Function` (Python 3.12). Unlike the static-scan
 * lane (a container image because it bundles four tools), this lane's runtime deps
 * are stdlib + boto3 (provided by the runtime) — no Docker build box is needed.
 * The no-Docker rule (RD-001) is about the DETONATION HOST, and this lane honours it:
 * the artifact runs directly on the ephemeral EC2, never in a container.
 *
 * IAM (least-privilege, modelled on the 2.0 orchestrator role): `ec2:RunInstances`
 * from the launch template (+ tag/terminate/describe the hosts it creates),
 * `ssm:SendCommand` + Get/List invocation, read the 2.0-published SSM coordinates,
 * PassRole ONLY the detonation instance role to EC2, read the artifact + write the
 * `runs/` log in the Forensic bucket, and `sqs:SendMessage` to EXACTLY the one Hub
 * ingest queue. No other Hub access; one-directional (RD-013).
 *
 * Zero-trust: the raw artifact + full command log never leave Forensic; only the
 * bounded outcome crosses, and it carries NO verdict — a run is EVIDENCE.
 */

const FORENSIC_ACCOUNT_ID = "360999005254";
const AMI_SSM_PREFIX = "/ztie/detonation";

export interface ZtieDetonationStackProps extends StackProps {
  /** Forensic artifact bucket name (intake stack output `ArtifactBucketName`). */
  readonly artifactBucketName: string;
  /** Forensic detonation work queue URL (intake output `DetonationQueueUrl`). */
  readonly detonationQueueUrl: string;
  /** Forensic detonation work queue ARN (intake output `DetonationQueueArn`). */
  readonly detonationQueueArn: string;
  /** Hub ingest queue URL (Hub output `IngestQueueUrl`) — the outcome crosses here. */
  readonly hubIngestQueueUrl: string;
  /** Hub ingest queue ARN (Hub output `IngestQueueArn`) — scopes the send grant. */
  readonly hubIngestQueueArn: string;
  /**
   * The Story 2.0 detonation instance role ARN (forensic-infra output
   * `DetonationInstanceRoleArn`). Scopes the PassRole grant to EXACTLY that role.
   */
  readonly detonationInstanceRoleArn: string;
  /**
   * Hard TTL (minutes) the 2.0 launch template enforces via `shutdown -h +N`. The
   * lane only RECORDS it in the outcome; it does not set it. Defaults to 5 (RD-007).
   */
  readonly hardTtlMinutes?: number;
}

export class ZtieDetonationStack extends Stack {
  /** The detonation Lambda's role ARN — register it as a Hub-queue sender. */
  public readonly detonationOrchestratorRoleArn: string;

  constructor(scope: Construct, id: string, props: ZtieDetonationStackProps) {
    super(scope, id, props);

    // Guard: this lane launches the host that EXECUTES the artifact, so it must be
    // in Forensic (RD-008). Warn (not hard-fail) so account-less synth/CI works.
    if (props?.env?.account && props.env.account !== FORENSIC_ACCOUNT_ID) {
      Annotations.of(this).addWarning(
        `ZTIE detonation lane is intended for the Forensic account ` +
          `${FORENSIC_ACCOUNT_ID} (it executes the artifact, RD-008); deploying ` +
          `into ${props.env.account}. Detonation must be contained in Forensic. ` +
          `Confirm this is intentional.`,
      );
    }

    const hardTtlMinutes = props.hardTtlMinutes ?? 5;

    // --- Imports (all in the Forensic account) -----------------------------
    const artifactBucket = s3.Bucket.fromBucketName(
      this,
      "ImportedArtifactBucket",
      props.artifactBucketName,
    );
    const detonationQueue = sqs.Queue.fromQueueArn(
      this,
      "ImportedDetonationQueue",
      props.detonationQueueArn,
    );

    // --- Lambda: the detonation orchestrator (PLAIN ZIP, py3.12) -----------
    const detonationFn = new lambda.Function(this, "DetonationOrchestrator", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "..", "..", "lambdas", "detonation"),
      ),
      // Modest — the orchestrator mostly waits on EC2/SSM; the WORK happens on the
      // ephemeral host, not here.
      memorySize: 512,
      // Below the detonation work queue's 900s visibility timeout. Covers launch +
      // SSM-online wait + host-native execution + teardown observation, all well
      // under the host's 5-min hard TTL.
      timeout: Duration.seconds(840),
      ephemeralStorageSize: Size.mebibytes(512),
      logRetention: logs.RetentionDays.ONE_MONTH,
      environment: {
        // The one-directional Forensic -> Hub door (same queue as the other
        // envelopes). Only the bounded run OUTCOME crosses here.
        HUB_INGEST_QUEUE_URL: props.hubIngestQueueUrl,
        // Story 2.3: the dynamic-run outcome contract version (its OWN pin — a new
        // envelope kind never rides the shared CONTRACT_VERSION).
        DYNAMIC_RUN_CONTRACT_VERSION: "1.0",
        // Story 2.4: the behavioral-telemetry contract version (its OWN pin — the
        // eighth envelope kind never rides the shared CONTRACT_VERSION or the run's
        // pin). The bounded, verdict-free syscall/network/filesystem summary crosses
        // to the Hub under this pin; the full trace stays in Forensic (RD-009).
        BEHAVIOR_CONTRACT_VERSION: "1.0",
        // Story 2.5: the SANITIZED-telemetry contract version (its OWN pin — the
        // ninth envelope kind never rides the shared CONTRACT_VERSION or any other
        // kind's pin). The bounded, verdict-free, entropy-scrubbed, noise-suppressed,
        // <=25K-token sanitized view of the 2.4 raw trace crosses to the Hub under
        // this pin; the full raw trace stays in Forensic (RD-009).
        SANITIZED_TELEMETRY_CONTRACT_VERSION: "1.0",
        // Story 2.5: the Phase-3 token budget the sanitized view is bounded to
        // (<=25K). Deterministic truncation keeps events in trace order until this
        // budget is reached, then records the truncated flag.
        SANITIZE_TOKEN_BUDGET: "25000",
        // Story 2.4: prefix under which the FULL behavioral trace is written in the
        // Forensic bucket (it stays in Forensic, RD-009; only the summary crosses).
        TRACES_PREFIX: "traces/",
        // The 2.0-published detonation coordinates the lane reads (no hard-coded
        // infrastructure ids in the code).
        LAUNCH_TEMPLATE_ID_PARAM: `${AMI_SSM_PREFIX}/launch-template-id`,
        ISOLATED_SUBNET_IDS_PARAM: `${AMI_SSM_PREFIX}/isolated-subnet-ids`,
        // RD-027 (two-tier): coordinates for the EPHEMERAL endpoint tier
        // (logs/sqs/bedrock-runtime) this lane creates per run. The SSM control
        // channel is always-on and needs no per-run action.
        VPC_ID_PARAM: `${AMI_SSM_PREFIX}/vpc-id`,
        ENDPOINT_SERVICE_NAMES_PARAM: `${AMI_SSM_PREFIX}/endpoint-service-names`,
        ENDPOINT_SECURITY_GROUP_ID_PARAM: `${AMI_SSM_PREFIX}/endpoint-security-group-id`,
        // The hard TTL the 2.0 UserData enforces (RD-007); recorded in the outcome.
        HARD_TTL_MINUTES: String(hardTtlMinutes),
        RUNS_PREFIX: "runs/",
        LOG_LEVEL: "INFO",
      },
    });
    this.detonationOrchestratorRoleArn = detonationFn.role!.roleArn;

    // Consume the Forensic detonation work queue. One artifact per invocation keeps
    // a slow/failing detonation isolated and bounds concurrent ephemeral hosts.
    detonationFn.addEventSource(
      new SqsEventSource(detonationQueue, {
        batchSize: 1,
        reportBatchItemFailures: true,
      }),
    );

    // --- Least-privilege grants (modelled on the 2.0 orchestrator role) ----
    // (1) Launch + manage the ephemeral detonation hosts. The launch template is
    //     the real guardrail (isolated subnet, no key pair, IMDSv2, TTL UserData);
    //     scope by account/region. RunInstances touches many sub-resources so it
    //     cannot be resource-scoped tightly here.
    detonationFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "RunAndManageEphemeralDetonationHosts",
        effect: iam.Effect.ALLOW,
        actions: [
          "ec2:RunInstances",
          "ec2:CreateTags",
          "ec2:TerminateInstances",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeLaunchTemplates",
          "ec2:DescribeLaunchTemplateVersions",
        ],
        resources: ["*"],
        conditions: {
          StringEquals: { "aws:RequestedRegion": this.region },
        },
      }),
    );

    // (2) Host-native SSM command channel (RD-001): send the command + read the
    //     invocation, and see which instances are SSM-managed.
    // RD-027: create/delete the EPHEMERAL endpoint tier (logs/sqs/bedrock-runtime)
    // per run. Region-scoped; grants NO IGW/NAT/route creation. The Describe verbs
    // support teardown + the tag-scoped start-of-run orphan sweep.
    detonationFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "ManageEphemeralInterfaceEndpoints",
        effect: iam.Effect.ALLOW,
        actions: [
          "ec2:CreateVpcEndpoint",
          "ec2:DeleteVpcEndpoints",
          "ec2:DescribeVpcEndpoints",
          "ec2:CreateTags",
        ],
        resources: ["*"],
        conditions: {
          StringEquals: { "aws:RequestedRegion": this.region },
        },
      }),
    );

    detonationFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "HostNativeSsmCommandChannel",
        effect: iam.Effect.ALLOW,
        actions: [
          "ssm:SendCommand",
          "ssm:GetCommandInvocation",
          "ssm:ListCommandInvocations",
          "ssm:ListCommands",
          "ssm:DescribeInstanceInformation",
        ],
        resources: ["*"],
        conditions: {
          StringEquals: { "aws:RequestedRegion": this.region },
        },
      }),
    );

    // (3) Read the 2.0-published detonation coordinates (launch-template id /
    //     isolated subnet ids / instance-role arn). Scoped to the /ztie/detonation
    //     parameter prefix.
    detonationFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "ReadDetonationCoordinates",
        effect: iam.Effect.ALLOW,
        actions: ["ssm:GetParameter", "ssm:GetParameters"],
        resources: [
          `arn:${this.partition}:ssm:${this.region}:${this.account}:parameter${AMI_SSM_PREFIX}/*`,
        ],
      }),
    );

    // (4) PassRole: the lane may hand ONLY the 2.0 detonation instance role to a
    //     launched host, and only to EC2. Nothing broader.
    detonationFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "PassDetonationInstanceRoleToEc2",
        effect: iam.Effect.ALLOW,
        actions: ["iam:PassRole"],
        resources: [props.detonationInstanceRoleArn],
        conditions: {
          StringEquals: { "iam:PassedToService": "ec2.amazonaws.com" },
        },
      }),
    );

    // (5) Read the raw artifact it detonates + write the full command log back
    //     under runs/ (both in the Forensic artifact bucket — the log STAYS in
    //     Forensic, RD-009). grantRead covers head/get + presign; grantPut(runs/*).
    artifactBucket.grantRead(detonationFn);
    artifactBucket.grantPut(detonationFn, "runs/*");
    // Story 2.4: write the FULL behavioral trace under traces/ (stays in Forensic,
    // RD-009 — only the bounded, derived behavioral SUMMARY crosses to the Hub).
    artifactBucket.grantPut(detonationFn, "traces/*");

    // (6) Cross to the Hub: EXACTLY sqs:SendMessage on EXACTLY the one Hub ingest
    //     queue (least-privilege, one-directional, RD-013). No other Hub access.
    detonationFn.addToRolePolicy(
      new iam.PolicyStatement({
        sid: "SendRunOutcomeToHubIngestQueue",
        effect: iam.Effect.ALLOW,
        actions: ["sqs:SendMessage"],
        resources: [props.hubIngestQueueArn],
      }),
    );

    // --- Outputs -----------------------------------------------------------
    new CfnOutput(this, "DetonationFunctionName", {
      value: detonationFn.functionName,
      description:
        "Detonation lane Lambda name (Story 2.3). Tail its logs to see the launched instance id, SSM command id, outcome, and teardown observation per intake_id.",
    });
    new CfnOutput(this, "DetonationOrchestratorRoleArn", {
      value: this.detonationOrchestratorRoleArn,
      description:
        "Detonation Lambda execution role ARN. Pass as forensicDetonationRoleArn to the Hub stack so it is a send-only principal on the Hub ingest queue (tightest least-privilege).",
    });
  }
}
