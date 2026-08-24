# ZTIE Infrastructure (CDK v2, TypeScript)

AWS-native infrastructure for the ZTIE Security Analysis Pipeline. Each phase's
resources are defined as CDK v2 stacks here; application (handler) code lives in
`../lambdas/` (Python 3.12).

## Stacks

| Stack | Story | Resources |
|-------|-------|-----------|
| `ZtieIntakeStack` | 1.1 | API Gateway (`POST /intake`, IAM auth) → intake Lambda → S3 artifact bucket + DynamoDB `intake` table (`status=RECEIVED`) |

## Prerequisites

- Node.js 18+ and npm.
- AWS credentials for the **Forensic account (360999005254)** with a region
  selected. ZTIE (intake + raw payload) is self-contained in Forensic — the blast
  zone (RD-008); do **not** deploy this into the Hub. The stack warns at synth time
  if the target is not Forensic.
- CDK bootstrap in the target account/region (one-time): `npx cdk bootstrap`.

## Install, synth, deploy

```bash
cd infra
npm install
npm run build          # tsc — type-checks against aws-cdk-lib
npx cdk synth          # render the CloudFormation template
npx cdk deploy ZtieIntakeStack
```

`cdk deploy` prints these outputs (used to validate Story 1.1 live):

- `IntakeEndpoint` — the `POST /intake` URL (SigV4-signed).
- `ArtifactBucketName` — the S3 bucket holding artifact bodies.
- `IntakeTableName` — the DynamoDB table holding intake records.

## Live validation (Story 1.1 DoD)

Because `/intake` uses **IAM (SigV4) auth**, the request must be signed by an AWS
principal that holds `execute-api:Invoke`. See the story brief
(`../DOCS/session-briefs/story-1.1-brief.md`) and the session close-out notes for
the exact copy-paste SigV4 submit + verify sequence.

## Teardown

```bash
npx cdk destroy ZtieIntakeStack
```

The S3 bucket and DynamoDB table use `RETAIN` removal policies (zero-trust: do not
silently drop received artifacts/records); delete them manually if a full teardown
is intended.
