<!-- FILE: docs/session-briefs/story-2.4S-attempt-3-LIVE-RUNBOOK.md -->
# Story 2.4S (Attempt 3) — LIVE validation runbook (stakeholder, CloudShell)
> Proves the detonation host uploads directly to S3 traces/ using the regional endpoint pinning and self-diagnosing logs. only YOU can run this; executor records verbatim; nothing on inference.

## Ground rules
- Run entirely in the Forensic Account (360999005254).
- `aws sts get-caller-identity` before every block.
- Run one line at a time.
- Region us-east-1, ambient creds.

## STEP 1 — Deploy the Updated ZtieDetonationStack
```bash
aws sts get-caller-identity
cd infra
export ARTIFACT_BUCKET=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --query 'Stacks[0].Outputs[?OutputKey==`ArtifactBucketName`].OutputValue' --output text)
npx cdk deploy ZtieDetonationStack -c artifactBucketName=$ARTIFACT_BUCKET --require-approval never
cd ..
```
(Literal output required: The CDK green UPDATE_COMPLETE or CREATE_COMPLETE showing the Lambda code updated.)

## STEP 2 — Stage Artifact & Prepare Direct Invoke
```bash
aws sts get-caller-identity
export INTAKE_ID="24s-live-test-3"

# Upload the test artifact to raw/
echo -e '#!/bin/bash\nsleep 5\necho "doing work"' > /tmp/2.4s-live-test.sh
aws s3 cp /tmp/2.4s-live-test.sh s3://$ARTIFACT_BUCKET/raw/$INTAKE_ID.sh

# Prepare the direct-invoke payload
cat <<EOF> /tmp/24s-payload-3.json
{
  "bucket": "$ARTIFACT_BUCKET",
  "key": "raw/$INTAKE_ID.sh",
  "intake_id": "$INTAKE_ID",
  "sha256": "dummyhash3",
  "artifact_class": "test"
}
EOF

export DETONATION_LAMBDA=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `ZtieDetonationStack`)].FunctionName' --output text)
echo "Target Lambda: $DETONATION_LAMBDA"
```
(Literal output required: Confirmation of the S3 upload and the extracted Detonation Lambda name.)

## STEP 3 — Execute the Detonation Lambda
```bash
aws sts get-caller-identity
# Invoke with a 240s read timeout so the CLI waits for the full detonation lifecycle
aws lambda invoke \
  --function-name $DETONATION_LAMBDA \
  --cli-read-timeout 240 \
  --payload fileb:///tmp/24s-payload-3.json \
  /tmp/24s-out-3.json

cat /tmp/24s-out-3.json | jq
```
(Literal output required: The full JSON response from the Lambda showing the execution outcome.)

## STEP 4 — Verify Regional S3 Deposit & Sentinel
```bash
aws sts get-caller-identity
aws s3api list-objects-v2 \
  --bucket $ARTIFACT_BUCKET \
  --prefix traces/24s-live-test-3/ \
  --query 'Contents[*].[Key, Size]' \
  --output table
```
(Literal output required: The S3 object keys. MUST show the behavior.strace.<pid> files AND the _UPLOAD_COMPLETE file.)

## Definition of Done
- [ ] DoD 3: ZtieDetonationStack successfully deployed.
- [ ] DoD 4: S3 deposit shows trace file(s) AND the _UPLOAD_COMPLETE sentinel in traces/24s-live-test-3/.
- [ ] DoD 5: Lambda output shows a successful capture_status and does not reflect a silent no_trace fallback.

## Verdict recording
[To be filled by Stakeholder/Human: PASS | FAIL | INCONCLUSIVE based on literal outputs above]
