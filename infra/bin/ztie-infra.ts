#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { ZtieIntakeStack } from "../lib/ztie-intake-stack";

const app = new cdk.App();

// The hub account (Pipeline-Hub, 641628980935) hosts the intake DynamoDB table
// per RD-008. Account/region resolve from the deploy-time CDK environment
// (CDK_DEFAULT_ACCOUNT/REGION) so the operator's active credentials pick the
// target; the expected hub account is asserted in the stack as a guard.
new ZtieIntakeStack(app, "ZtieIntakeStack", {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  description:
    "ZTIE Story 1.1 — Intake gateway: API Gateway (IAM auth) -> Lambda -> S3 + DynamoDB (status=RECEIVED).",
  tags: {
    Project: "ZTIE",
    Phase: "P1-Intake",
    Story: "1.1",
    ManagedBy: "CDK",
  },
});

app.synth();
