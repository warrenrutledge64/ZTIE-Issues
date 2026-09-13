#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { ZtieIntakeStack } from "../lib/ztie-intake-stack";
import { ZtieHubTrackingStack } from "../lib/ztie-hub-tracking-stack";
import {
  ZtieForensicInfraStack,
  AmiFlavor,
} from "../lib/ztie-forensic-infra-stack";
import { ZtieStaticScanStack } from "../lib/ztie-static-scan-stack";
import { ZtieDetonationStack } from "../lib/ztie-detonation-stack";
import { ZtieOrchestrationStack } from "../lib/ztie-orchestration-stack";
import { ZtieDashboardStack } from "../lib/ztie-dashboard-stack";

/**
 * ZTIE infrastructure app (Story 1.1 + 1.1R + 2.0).
 *
 * THREE stacks across the Hub + Forensic accounts:
 *   - ZtieHubTrackingStack   (Hub)      — durable record + RD-013 gate (deploy 1st)
 *   - ZtieIntakeStack        (Forensic) — intake gateway (deploy 2nd; needs Hub queue)
 *   - ZtieForensicInfraStack (Forensic) — Phase-2 shared infra foundation (Story
 *                                          2.0): isolated VPC + IAM + launch
 *                                          template + SSM + Bedrock. STANDALONE —
 *                                          no cross-account dependency; deploy any
 *                                          time with Forensic credentials.
 *
 * The Hub + intake stacks are deployed in a fixed order because the Forensic
 * intake stack must know the Hub ingest queue created by the Hub stack:
 *
 *   1) ZtieHubTrackingStack  -> Hub account (Pipeline-Hub, 641628980935)
 *        Durable tracking DynamoDB + the RD-013 validating gate (ingest SQS
 *        queue + DLQ + validator Lambda + quarantine S3). Deploy FIRST.
 *
 *   2) ZtieIntakeStack       -> Forensic account (360999005254)
 *        Intake API + raw-body S3 + the derived-envelope SQS send. Deploy
 *        SECOND, passing the Hub queue URL/ARN from step 1's outputs.
 *
 * Cross-account CDK cannot resolve the two stacks' references automatically
 * (separate accounts, separate deploys, separate credentials), so the wiring is
 * done via explicit context values captured from the Hub stack's outputs. Each
 * stack is only instantiated when the context needed to target its account is
 * present, so you can `cdk deploy` each one independently with the right creds.
 *
 * Context values (pass with -c KEY=VALUE, or set in cdk.context.json):
 *   hubAccount              Hub account id (default 641628980935)
 *   forensicAccount         Forensic account id (default 360999005254)
 *   region                  Region (default us-east-1 / CDK_DEFAULT_REGION)
 *   forensicIntakeRoleArn   (Hub stack, optional) intake Lambda role ARN for the
 *                           tightest send-only grant; from step-2 output
 *                           IntakeHandlerRoleArn on a re-deploy, or omit initially.
 *   hubIngestQueueUrl       (Forensic stack, REQUIRED) from Hub output IngestQueueUrl
 *   hubIngestQueueArn       (Forensic stack, REQUIRED) from Hub output IngestQueueArn
 */

const app = new cdk.App();

const HUB_ACCOUNT_DEFAULT = "641628980935";
const FORENSIC_ACCOUNT_DEFAULT = "360999005254";

const region =
  (app.node.tryGetContext("region") as string) ||
  process.env.CDK_DEFAULT_REGION ||
  "us-east-1";

const hubAccount =
  (app.node.tryGetContext("hubAccount") as string) || HUB_ACCOUNT_DEFAULT;
const forensicAccount =
  (app.node.tryGetContext("forensicAccount") as string) ||
  FORENSIC_ACCOUNT_DEFAULT;

const commonTags = {
  Project: "ZTIE",
  Phase: "P1-Intake",
  ManagedBy: "CDK",
};

// --- Stack 1: Hub tracking + data-contract gate (deploy FIRST, Hub account) ---
const forensicIntakeRoleArn = app.node.tryGetContext(
  "forensicIntakeRoleArn",
) as string | undefined;
// Story 1.2: the preprocessor Lambda is the SECOND Forensic-side sender on the
// Hub ingest queue (it emits the classification label). Pass its role ARN (from
// the Forensic stack output PreprocessorRoleArn on a re-deploy) for tightest
// least-privilege; omit it if the account-root send grant fallback is in effect.
const forensicPreprocessorRoleArn = app.node.tryGetContext(
  "forensicPreprocessorRoleArn",
) as string | undefined;
// Story 2.1: the static-scan Lambda is the THIRD Forensic-side sender on the Hub
// ingest queue (it emits the derived static-scan summary). Pass its role ARN (from
// the static-scan stack output StaticScanRoleArn on a re-deploy) for tightest
// least-privilege; omit it if the account-root send grant fallback is in effect.
const forensicStaticScanRoleArn = app.node.tryGetContext(
  "forensicStaticScanRoleArn",
) as string | undefined;

new ZtieHubTrackingStack(app, "ZtieHubTrackingStack", {
  env: { account: hubAccount, region },
  description:
    "ZTIE Story 1.1R (+1.2/1.3/1.4/2.1) — Hub durable tracking DynamoDB + RD-013 validating ingest gate (SQS + validator Lambda + quarantine); validates intake + classification + routing + reject + static-scan-summary envelopes.",
  forensicIntakeRoleArn,
  forensicPreprocessorRoleArn,
  forensicStaticScanRoleArn,
  tags: { ...commonTags, Story: "1.1R", Account: "Hub" },
});

// --- Stack 2: Forensic intake (deploy SECOND, Forensic account) --------------
// Only instantiate when the Hub queue coordinates are supplied, so a Hub-only
// deploy (step 1) doesn't fail synth for a missing queue URL.
const hubIngestQueueUrl = app.node.tryGetContext("hubIngestQueueUrl") as
  string | undefined;
const hubIngestQueueArn = app.node.tryGetContext("hubIngestQueueArn") as
  string | undefined;

// Story 2.6 (RD-029, OPTIONAL): the inspection-orchestration state-machine ARN
// (from the orchestration stack output InspectionStateMachineArn on a re-deploy).
// When supplied, the intake stack gives the preprocessor ORCHESTRATION_STATE_MACHINE_ARN
// + a scoped states:StartExecution grant so it starts ONE concurrent fork execution
// instead of the two independent enqueues. Omit on the first intake deploy (before
// the orchestration stack exists) — the preprocessor falls back (backward-safe).
const orchestrationStateMachineArn = app.node.tryGetContext(
  "orchestrationStateMachineArn",
) as string | undefined;

if (hubIngestQueueUrl && hubIngestQueueArn) {
  new ZtieIntakeStack(app, "ZtieIntakeStack", {
    env: { account: forensicAccount, region },
    description:
      "ZTIE Story 1.1 (+1.1R) — Intake gateway: API Gateway (IAM auth) -> Lambda -> Forensic S3 + derived-envelope send to Hub ingest queue.",
    hubIngestQueueUrl,
    hubIngestQueueArn,
    orchestrationStateMachineArn,
    tags: { ...commonTags, Story: "1.1", Account: "Forensic" },
  });
}

// --- Stack 3: Forensic Phase-2 infra foundation (Story 2.0) ------------------
// The shared network + IAM + launch-template bedrock all of Phase 2 stands on.
// It is STANDALONE — it has NO cross-account dependency (unlike the intake stack,
// which needs the Hub queue), so it always instantiates and deploys directly to
// the Forensic account with Forensic credentials. Optional context:
//   amiFlavor   OS flavor whose golden AMI the launch template resolves from
//               /ztie/ami/<flavor> (default ubuntu-22.04 — the one live in SSM).
const amiFlavor = app.node.tryGetContext("amiFlavor") as AmiFlavor | undefined;

new ZtieForensicInfraStack(app, "ZtieForensicInfraStack", {
  env: { account: forensicAccount, region },
  description:
    "ZTIE Story 2.0 — Phase-2 shared infra foundation in Forensic: isolated VPC (VPC endpoints only, zero internet egress) + IAM roles + ephemeral EC2 launch template (parametric AMI, 5-min hard TTL, host-native SSM) + SSM wiring + Bedrock Nova Pro access.",
  amiFlavor,
  // Story-specific Phase tag so this foundation is distinguishable from the
  // Phase-1 intake resources also in Forensic.
  tags: { ...commonTags, Phase: "P2-Infra", Story: "2.0", Account: "Forensic" },
});

// --- Stack 4: Forensic static-scan lane (Story 2.1, Forensic account) --------
// The non-executing static-analysis lane (cfn-lint/cfn-guard/checkov/bandit),
// packaged as a container-image Lambda (RD-021). It consumes the Forensic
// static-scan work queue (created in the intake stack), reads the raw artifact
// from the Forensic artifact bucket, writes the normalized findings document back
// under findings/ (stays in Forensic, RD-009), and crosses only a bounded summary
// to the Hub ingest queue (fifth envelope kind, RD-013).
//
// Only instantiate when the coordinates it imports are supplied (all Forensic-side
// except the Hub ingest queue). Deploy AFTER the intake + Hub stacks. Context:
//   artifactBucketName   (REQUIRED) from intake output ArtifactBucketName
//   staticScanQueueUrl   (REQUIRED) from intake output StaticScanQueueUrl
//   staticScanQueueArn   (REQUIRED) from intake output StaticScanQueueArn
//   hubIngestQueueUrl    (REQUIRED) from Hub output IngestQueueUrl (same as intake)
//   hubIngestQueueArn    (REQUIRED) from Hub output IngestQueueArn (same as intake)
//   cfnGuardVersion      (optional) cfn-guard binary version baked into the image
const artifactBucketName = app.node.tryGetContext("artifactBucketName") as
  string | undefined;
const staticScanQueueUrl = app.node.tryGetContext("staticScanQueueUrl") as
  string | undefined;
const staticScanQueueArn = app.node.tryGetContext("staticScanQueueArn") as
  string | undefined;
const cfnGuardVersion = app.node.tryGetContext("cfnGuardVersion") as
  string | undefined;

if (
  artifactBucketName &&
  staticScanQueueUrl &&
  staticScanQueueArn &&
  hubIngestQueueUrl &&
  hubIngestQueueArn
) {
  new ZtieStaticScanStack(app, "ZtieStaticScanStack", {
    env: { account: forensicAccount, region },
    description:
      "ZTIE Story 2.1 — static-analysis lane (Forensic): container-image Lambda running cfn-lint/cfn-guard/checkov/bandit (non-executing) over an artifact routed to static_analysis; normalized findings -> Forensic S3, bounded summary -> Hub ingest queue.",
    artifactBucketName,
    staticScanQueueUrl,
    staticScanQueueArn,
    hubIngestQueueUrl,
    hubIngestQueueArn,
    cfnGuardVersion,
    tags: {
      ...commonTags,
      Phase: "P2-Static",
      Story: "2.1",
      Account: "Forensic",
    },
  });
}

// --- Stack 5: Forensic detonation (DYNAMIC) lane (Story 2.3) ------------------
// The EXECUTING lane. A PLAIN ZIP Python Lambda (NO Docker build box needed — its
// runtime deps are stdlib + boto3): it consumes the Forensic detonation work queue
// (created in the intake stack), launches ONE ephemeral EC2 from the Story 2.0
// launch template via ec2:RunInstances, executes the artifact host-native via SSM
// (NO Docker on the host, RD-001), lets the host self-terminate on the 5-min hard
// TTL, writes the full command log to Forensic S3 under runs/ (stays in Forensic,
// RD-009), and crosses only a bounded, verdict-free run OUTCOME to the Hub ingest
// queue (sixth envelope kind, RD-013).
//
// Only instantiate when the coordinates it imports are supplied (all Forensic-side
// except the Hub ingest queue). Deploy AFTER the intake + Hub + forensic-infra (2.0)
// stacks. Context:
//   artifactBucketName          (REQUIRED) from intake output ArtifactBucketName
//   detonationQueueUrl          (REQUIRED) from intake output DetonationQueueUrl
//   detonationQueueArn          (REQUIRED) from intake output DetonationQueueArn
//   hubIngestQueueUrl           (REQUIRED) from Hub output IngestQueueUrl (same as intake)
//   hubIngestQueueArn           (REQUIRED) from Hub output IngestQueueArn (same as intake)
//   detonationInstanceRoleArn   (REQUIRED) from forensic-infra output DetonationInstanceRoleArn
//   hardTtlMinutes              (optional) the 2.0 launch-template TTL (default 5)
const detonationQueueUrl = app.node.tryGetContext("detonationQueueUrl") as
  string | undefined;
const detonationQueueArn = app.node.tryGetContext("detonationQueueArn") as
  string | undefined;
const detonationInstanceRoleArn = app.node.tryGetContext(
  "detonationInstanceRoleArn",
) as string | undefined;
const hardTtlMinutesCtx = app.node.tryGetContext("hardTtlMinutes") as
  string | undefined;

if (
  artifactBucketName &&
  detonationQueueUrl &&
  detonationQueueArn &&
  detonationInstanceRoleArn &&
  hubIngestQueueUrl &&
  hubIngestQueueArn
) {
  new ZtieDetonationStack(app, "ZtieDetonationStack", {
    env: { account: forensicAccount, region },
    description:
      "ZTIE Story 2.3 — dynamic (detonation) lane (Forensic): plain-zip Lambda that launches ONE ephemeral EC2 from the 2.0 launch template, executes the artifact host-native via SSM (no Docker), self-terminates on the 5-min hard TTL, and crosses a bounded verdict-free run outcome to the Hub ingest queue.",
    artifactBucketName,
    detonationQueueUrl,
    detonationQueueArn,
    hubIngestQueueUrl,
    hubIngestQueueArn,
    detonationInstanceRoleArn,
    hardTtlMinutes: hardTtlMinutesCtx ? Number(hardTtlMinutesCtx) : undefined,
    tags: {
      ...commonTags,
      Phase: "P2-Dynamic",
      Story: "2.3",
      Account: "Forensic",
    },
  });
}

// --- Stack 6: Forensic inspection orchestration (Story 2.6, Forensic account) ---
// The CONCURRENT FORK + both-complete JOIN (RD-029). A Step Functions STANDARD state
// machine whose Parallel state fans out to the static lane (2.1/2.2) and the dynamic
// lane (2.3) concurrently — each branch with a per-branch error Catch — and a terminal
// join task that invokes the collector (join) Lambda, which crosses ONE bounded,
// verdict-free collected record (the 7th RD-013 envelope kind) to the Hub ingest queue.
//
// It only ORCHESTRATES the existing lanes — it does NOT re-implement either lane or
// touch the detonation launch/execute internals. Only instantiate when the coordinates
// it imports are supplied (all Forensic-side except the Hub ingest queue). Deploy AFTER
// the intake + Hub + static-scan + detonation stacks (it invokes those two lane
// Lambdas), then RE-DEPLOY the intake stack passing this stack's output
// InspectionStateMachineArn as -c orchestrationStateMachineArn so the preprocessor
// switches from the independent enqueues to the concurrent fork. Context:
//   staticScanFunctionArn   (REQUIRED) the static-scan lane Lambda ARN
//   detonationFunctionArn   (REQUIRED) the detonation lane Lambda ARN
//   artifactBucketName      (REQUIRED) from intake output ArtifactBucketName
//   hubIngestQueueUrl       (REQUIRED) from Hub output IngestQueueUrl (same as intake)
//   hubIngestQueueArn       (REQUIRED) from Hub output IngestQueueArn (same as intake)
const staticScanFunctionArn = app.node.tryGetContext(
  "staticScanFunctionArn",
) as string | undefined;
const detonationFunctionArn = app.node.tryGetContext(
  "detonationFunctionArn",
) as string | undefined;

if (
  staticScanFunctionArn &&
  detonationFunctionArn &&
  artifactBucketName &&
  hubIngestQueueUrl &&
  hubIngestQueueArn
) {
  new ZtieOrchestrationStack(app, "ZtieOrchestrationStack", {
    env: { account: forensicAccount, region },
    description:
      "ZTIE Story 2.6 (RD-029) — inspection orchestration (Forensic): Step Functions Standard state machine with a Parallel state (static + dynamic branches, per-branch error Catch) and a terminal collector join that crosses ONE bounded verdict-free collected record to the Hub ingest queue.",
    staticScanFunctionArn,
    detonationFunctionArn,
    artifactBucketName,
    hubIngestQueueUrl,
    hubIngestQueueArn,
    tags: {
      ...commonTags,
      Phase: "P2-Orchestration",
      Story: "2.6",
      Account: "Forensic",
    },
  });
}

// --- Stack 7: Hub real-time dashboard render (Story 4.3, Hub account) --------
// The Phase-4 PRESENTATION layer (RD-043). A static single-page dashboard (dark theme,
// vanilla HTML/CSS/JS — no npm build) served from a private S3 bucket behind CloudFront
// (OAC), plus a GET API Gateway front (IAM auth) that proxies to the EXISTING Story 4.2
// `hub_dashboard` orchestrator Lambda UNCHANGED (GET /dashboard = fleet view, GET
// /status/{intake_id} = per-intake view). It RENDERS 4.2's `dashboard.contract.v1`
// payload; it re-derives nothing, calls no model, and enforces nothing (the human
// accept/reject ACTION is Story 4.4). It references the 4.2 Lambda by ARN, so it does
// NOT modify the Hub tracking stack. Deploy into the Hub account with Hub credentials
// AFTER the Hub tracking stack (whose DashboardOrchestratorName output names the 4.2
// Lambda). Only instantiate when its ARN is supplied. Context:
//   dashboardFunctionArn   (REQUIRED) the 4.2 hub_dashboard Lambda ARN (build the ARN
//                          from the Hub output DashboardOrchestratorName +
//                          arn:aws:lambda:<region>:<hubAccount>:function:<name>).
//   subscriberId           (optional) the subscriber this dashboard is scoped to
//                          (RD-028; default "ztie-tenant-zero").
const dashboardFunctionArn = app.node.tryGetContext("dashboardFunctionArn") as
  string | undefined;
const dashboardSubscriberId = app.node.tryGetContext("subscriberId") as
  string | undefined;

if (dashboardFunctionArn) {
  new ZtieDashboardStack(app, "ZtieDashboardStack", {
    env: { account: hubAccount, region },
    description:
      "ZTIE Story 4.3 (RD-043) — real-time dashboard render (Hub): static dark-theme SPA (S3 + CloudFront OAC) + IAM-auth GET API front (GET /dashboard, GET /status/{intake_id}) proxying to the UNCHANGED 4.2 hub_dashboard Lambda. Renders dashboard.contract.v1; no re-derivation, no model call, no enforcement (the accept/reject action is 4.4).",
    dashboardFunctionArn,
    subscriberId: dashboardSubscriberId,
    tags: {
      ...commonTags,
      Phase: "P4-Dashboard",
      Story: "4.3",
      Account: "Hub",
    },
  });
}

app.synth();
