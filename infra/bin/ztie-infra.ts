#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { ZtieIntakeStack } from "../lib/ztie-intake-stack";
import { ZtieHubTrackingStack } from "../lib/ztie-hub-tracking-stack";

/**
 * ZTIE infrastructure app (Story 1.1 + 1.1R).
 *
 * TWO stacks, TWO accounts — deployed in a fixed order because the Forensic
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

new ZtieHubTrackingStack(app, "ZtieHubTrackingStack", {
  env: { account: hubAccount, region },
  description:
    "ZTIE Story 1.1R — Hub durable tracking DynamoDB + RD-013 validating ingest gate (SQS + validator Lambda + quarantine).",
  forensicIntakeRoleArn,
  tags: { ...commonTags, Story: "1.1R", Account: "Hub" },
});

// --- Stack 2: Forensic intake (deploy SECOND, Forensic account) --------------
// Only instantiate when the Hub queue coordinates are supplied, so a Hub-only
// deploy (step 1) doesn't fail synth for a missing queue URL.
const hubIngestQueueUrl = app.node.tryGetContext("hubIngestQueueUrl") as
  string | undefined;
const hubIngestQueueArn = app.node.tryGetContext("hubIngestQueueArn") as
  string | undefined;

if (hubIngestQueueUrl && hubIngestQueueArn) {
  new ZtieIntakeStack(app, "ZtieIntakeStack", {
    env: { account: forensicAccount, region },
    description:
      "ZTIE Story 1.1 (+1.1R) — Intake gateway: API Gateway (IAM auth) -> Lambda -> Forensic S3 + derived-envelope send to Hub ingest queue.",
    hubIngestQueueUrl,
    hubIngestQueueArn,
    tags: { ...commonTags, Story: "1.1", Account: "Forensic" },
  });
}

app.synth();
