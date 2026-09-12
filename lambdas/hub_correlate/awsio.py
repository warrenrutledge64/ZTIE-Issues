"""ZTIE Story 3.2 — thin AWS I/O seam for the Hub-side Nova Pro correlation engine.

ALL boto3 lives HERE so the correlation logic (``correlate.py``) stays pure and
offline-unit-testable (the proven 1.2 -> 3.1 lane pattern: pure logic + a thin boto3
seam). Nothing in this module builds a prompt, parses a model response, or makes a
correlation/verdict decision; it only (a) invokes Amazon Nova Pro on
``bedrock-runtime`` with real EXPONENTIAL-BACKOFF RETRY on throttling/5xx, and
(b) reads the Hub tracking item + writes the derived correlation result back onto
the SAME item.

This runs in the HUB account (Pipeline-Hub, 641628980935). It touches ONLY the Hub
tracking DynamoDB table and the Bedrock runtime endpoint. It NEVER reads the
Forensic S3 body / findings / trace (it cannot and must not — RD-009); its input is
already-derived, already-Hub data (the 3.1 combined event on the tracking item).
There is NO Forensic -> Hub crossing here (RD-013 is untouched): the correlation
result never leaves the Hub.

The retry is REAL, bounded, jittered, and inspectable: ``invoke_nova`` returns the
number of attempts it made so the caller can record it on the result (the retry is
observable, not a single silent call). RD-003 requires exponential-backoff retry on
Bedrock throttling.
"""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Reused across warm invocations.
_ddb_table = None
_bedrock = None

# Bedrock error codes that are RETRYABLE with exponential backoff (RD-003). Anything
# else (validation error, access denied, unknown model) is NOT retried — retrying a
# deterministic failure only wastes time + money.
_RETRYABLE_ERROR_CODES = frozenset(
    {
        "ThrottlingException",
        "TooManyRequestsException",
        "ServiceUnavailableException",
        "ServiceUnavailable",
        "InternalServerException",
        "ModelTimeoutException",
        "ModelNotReadyException",
    }
)


def table(table_name: str):
    global _ddb_table
    if _ddb_table is None:
        _ddb_table = boto3.resource("dynamodb").Table(table_name)
    return _ddb_table


def _bedrock_client():
    global _bedrock
    if _bedrock is None:
        # botocore already retries throttling internally; we ALSO do an explicit,
        # inspectable application-level backoff loop (RD-003 requires it be
        # inspectable/counted), so keep the SDK's own retries minimal to avoid
        # double-compounding and to keep the attempt count meaningful.
        _bedrock = boto3.client(
            "bedrock-runtime",
            config=Config(retries={"max_attempts": 1, "mode": "standard"}),
        )
    return _bedrock


def get_item(table_name: str, intake_id: str) -> dict[str, Any] | None:
    """Read the Hub tracking item by intake_id. Returns the item dict or None."""
    return table(table_name).get_item(Key={"intake_id": intake_id}).get("Item")


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        if code in _RETRYABLE_ERROR_CODES:
            return True
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        # Any 5xx is retryable; 429 is throttling.
        return isinstance(status, int) and (status >= 500 or status == 429)
    # Read/connection timeouts from botocore are retryable.
    return exc.__class__.__name__ in {
        "ReadTimeoutError",
        "ConnectTimeoutError",
        "EndpointConnectionError",
    }


def invoke_nova(
    *,
    model_id: str,
    body: dict[str, Any],
    max_attempts: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 20.0,
    sleep=time.sleep,
) -> tuple[dict[str, Any], int, int]:
    """Invoke Amazon Nova Pro via bedrock-runtime InvokeModel with real
    EXPONENTIAL-BACKOFF + jitter retry on throttling / 5xx (RD-003).

    Returns ``(response_body, attempts, latency_ms)`` where ``response_body`` is the
    parsed JSON body of the successful call, ``attempts`` is how many invocations
    were made (>=1; >1 means it retried — the retry is inspectable), and
    ``latency_ms`` is the wall-clock of the final (successful) call. Raises the last
    exception if the retry budget is exhausted or the error is non-retryable — the
    caller catches that and records status 'model_error' (never fabricates a
    correlation).

    ``sleep`` is injectable so tests can exercise the backoff loop without real
    waiting.
    """
    client = _bedrock_client()
    payload = json.dumps(body).encode("utf-8")
    last_exc: Exception | None = None
    attempts = 0
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        try:
            started = time.monotonic()
            resp = client.invoke_model(
                modelId=model_id,
                body=payload,
                contentType="application/json",
                accept="application/json",
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            raw = resp["body"].read()
            response_body = json.loads(raw)
            return response_body, attempts, latency_ms
        except Exception as exc:  # classify then decide
            last_exc = exc
            if not _is_retryable(exc) or attempt == max_attempts:
                logger.warning(
                    "Nova invoke failed (attempt %d/%d, retryable=%s): %s",
                    attempt,
                    max_attempts,
                    _is_retryable(exc),
                    exc,
                )
                raise
            # Exponential backoff with full jitter, capped.
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = random.uniform(0, delay)
            logger.info(
                "Nova invoke retryable failure (attempt %d/%d); backing off %.2fs: %s",
                attempt,
                max_attempts,
                delay,
                exc,
            )
            sleep(delay)
    # Unreachable (the loop either returns or raises), but keep mypy/readers happy.
    assert last_exc is not None
    raise last_exc


def put_correlation_result(
    table_name: str,
    *,
    intake_id: str,
    sha256: str,
    correlation_result: dict[str, Any],
    correlated_at: str,
    status: str,
) -> None:
    """Write the derived correlation result back onto the EXISTING tracking record.

    Integrity-bound exactly like every other Hub write path: the update requires the
    record to already exist AND its stored ``sha256`` to equal the artifact the
    correlation was built over (so a correlation can only attach to the exact
    tracked artifact). It NEVER creates a record and NEVER touches ``status`` /
    verdict — the correlation result is EVIDENCE, not a decision. It sets the derived
    ``correlation_result`` object, a flattened ``correlation_status`` for convenient
    dashboard/query use, and ``correlated_at``.

    A ``ConditionalCheckFailedException`` here means the item vanished or its sha256
    changed between the read and the write (a race); the caller treats that as a
    benign no-op (a later stream event re-derives).
    """
    table(table_name).update_item(
        Key={"intake_id": intake_id},
        UpdateExpression=(
            "SET correlation_result = :cr, correlation_status = :cs, "
            "correlated_at = :ca"
        ),
        ConditionExpression="attribute_exists(intake_id) AND sha256 = :sha",
        ExpressionAttributeValues={
            ":cr": correlation_result,
            ":cs": status,
            ":ca": correlated_at,
            ":sha": sha256,
        },
    )
