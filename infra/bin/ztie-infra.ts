#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { ZtieIntakeStack } from "../lib/ztie-intake-stack";

const app = new cdk.App();

// The Forensic account (360999005254) hosts the intake gateway, the raw artifact
// S3 bucket, and the intake DynamoDB record per RD-008/009 — ZTIE is self-contained
// in Forensic (the blast zone); the Hub never stores the raw payload. Account/region
// resolve from the deploy-time CDK environment (CDK_DEFAULT_ACCOUNT/REGION) so the
// operator's active credentials pick the target; the expected Forensic account is
// asserted in the stack as a synth-time guard.
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
