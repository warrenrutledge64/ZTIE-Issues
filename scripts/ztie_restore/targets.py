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
            },
        )
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
