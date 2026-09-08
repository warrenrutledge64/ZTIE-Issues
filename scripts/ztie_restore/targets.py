"""Capture targets for the real deployed ZTIE pipeline (Story 1.R).

This is the declarative inventory of *what durable state to capture*, per account.
It reflects the Phase-1 deployed shape after Story 1.1R (durable record in the
Hub; Forensic holds only ephemeral state):

- **Hub** (Pipeline-Hub, 641628980935) — ``ZtieHubTrackingStack``:
  the DURABLE tracking DynamoDB, the ingest SQS queue + DLQ, the validator Lambda,
  and the quarantine S3 bucket. This is the account whose durable record RD-012
  says must survive a Forensic teardown, so it is the primary restore target.

- **Forensic** (360999005254) — ``ZtieIntakeStack``:
  the intake API + intake Lambda + the raw-artifact S3 bucket. Forensic's
  *ephemeral* content (the raw payload bodies, per-run scratch) is DISPOSABLE and
  is NOT restored — it is rebuilt. What 1.R captures for Forensic is the stack
  projection (so the intake infrastructure is restorable), never the payload data.

Resource *names* (the S3 bucket names, the DynamoDB table name, the Lambda
function names) are CDK-generated and therefore only known at deploy time. Rather
than hardcode guesses, targets declare the CloudFormation stack and the *logical
ids* to resolve; capture asks CloudFormation for the physical ids at run time.
This keeps the tool correct against the actually-deployed stacks with no manual
name-copying, and it means the stack projection (template hash + params + tags) is
always captured even before per-resource projections are resolved.

The two stacks are the source of truth; per-resource projections are resolved from
their stack resources by logical id.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StackTarget:
    """A CloudFormation stack to capture, plus the resources to project from it."""

    stack_name: str
    #: logical id -> resource kind. Kinds: "dynamodb", "lambda", "s3".
    resources: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AccountTarget:
    """One account's capture plan (label + expected id + its stacks + SSM params)."""

    label: str
    account_id: str
    stacks: list[StackTarget] = field(default_factory=list)
    #: SSM parameter names to capture (none in P1; kept for P2+ reuse).
    ssm_parameters: list[str] = field(default_factory=list)


# The CloudFormation logical ids come from the CDK constructs in
# infra/lib/*.ts. CDK suffixes them with a hash in the physical id, but the
# logical id prefix is stable and resolvable via describe_stack_resources.
HUB = AccountTarget(
    label="hub",
    account_id="641628980935",
    stacks=[
        StackTarget(
            stack_name="ZtieHubTrackingStack",
            resources={
                "TrackingTable": "dynamodb",
                "QuarantineBucket": "s3",
                "IngestValidator": "lambda",
            },
        )
    ],
)

FORENSIC = AccountTarget(
    label="forensic",
    account_id="360999005254",
    stacks=[
        StackTarget(
            stack_name="ZtieIntakeStack",
            resources={
                "IntakeArtifactBucket": "s3",
                "IntakeHandler": "lambda",
                # Story 1.2/1.3/1.4: the preprocessor Lambda (classify + route +
                # safe-reject) also lives in this stack.
                "PreprocessorHandler": "lambda",
                # Story 2.1: the intra-Forensic static-scan work queue + DLQ were
                # added to this stack. They are captured at the STACK level (the
                # stack projection = template hash + params + tags covers their
                # desired state); no per-resource SQS projection kind is used
                # unless a future need requires finer drift detection.
            },
        ),
        # Story 2.1: the static-analysis lane — a container-image Lambda in its own
        # stack. Stack-level projection covers the whole stack; the Lambda is also
        # projected per-resource (code_sha256 etc.) since the "lambda" kind exists.
        StackTarget(
            stack_name="ZtieStaticScanStack",
            resources={
                "StaticScanFunction": "lambda",
            },
        ),
        # Story 2.0 / 2.0E: the Phase-2 shared infra foundation (isolated VPC, IAM,
        # the ephemeral-EC2 launch template, SSM wiring). Captured at the STACK level
        # (template hash + params + tags) plus its published SSM parameters below.
        # 2.0 was validated live (Story A.2, 2026-09-02) and RESHAPED by Story 2.0E
        # (RD-027, validated 2026-09-08): the always-on interface endpoints were split
        # into a single-AZ always-on SSM control channel + three ephemeral service
        # names published to SSM (captured below). Capturing its deployed state here
        # BACKS IT UP for the story-2.0E restore point (capture never validates, it
        # only snapshots the desired-state projection).
        StackTarget(
            stack_name="ZtieForensicInfraStack",
            resources={},
        ),
        # Story 2.3 / 2.0E: the detonation orchestrator stack (the Lambda that runs
        # the RD-027 ephemeral-endpoint lifecycle + sweep + host-native SSM
        # execution). Its Lambda code changed materially in 2.0E (the two-tier
        # endpoint seam + the conflicting-DNS-domain create-retry fix), so it is a
        # first-class part of the story-2.0E deployed-state baseline. Stack-level
        # projection (template hash + params + tags) + the orchestrator Lambda
        # per-resource (code_sha256). NOTE: this stack only exists when deployed with
        # its -c context; capture refuses if a target stack is not deployed, so
        # ensure ZtieDetonationStack is deployed before capturing (it is, post-2.0E).
        StackTarget(
            stack_name="ZtieDetonationStack",
            resources={
                "DetonationOrchestrator": "lambda",
            },
        ),
    ],
    # Story 2.0 publishes these ZTIE-owned detonation-coordination parameters; the
    # SSM projection kind already exists, so capture them for restore. Story 2.0E
    # (RD-027) adds the three two-tier coordinates the orchestrator reads to build the
    # ephemeral endpoint tier (vpc id + ordered service names + endpoint SG id) — they
    # are desired-state the restore point must pin, so they are captured here too.
    ssm_parameters=[
        "/ztie/detonation/launch-template-id",
        "/ztie/detonation/instance-role-arn",
        "/ztie/detonation/isolated-subnet-ids",
        "/ztie/detonation/ami-flavor",
        # Story 2.0E (RD-027) — the ephemeral-endpoint-tier coordinates:
        "/ztie/detonation/vpc-id",
        "/ztie/detonation/endpoint-service-names",
        "/ztie/detonation/endpoint-security-group-id",
    ],
)

#: Look up an account target by its CLI label.
ACCOUNTS: dict[str, AccountTarget] = {HUB.label: HUB, FORENSIC.label: FORENSIC}


def resolve_account(label: str) -> AccountTarget:
    """Return the AccountTarget for ``label`` or raise a clear error."""
    try:
        return ACCOUNTS[label]
    except KeyError:
        valid = ", ".join(sorted(ACCOUNTS))
        raise ValueError(f"unknown account '{label}' (expected one of: {valid})") from None
