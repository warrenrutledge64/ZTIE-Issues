"""ZTIE Story H.2 (RD-048/RD-049) — the real ECDSA signature verifier (bundled crypto).

This is the ONE part of the decision-auth library that needs a third-party crypto
dependency (``cryptography``) — it verifies a KMS-produced ECDSA-P256/SHA-256 detached
signature against the Hub's public key, entirely OFFLINE (no call to KMS, no call to
the Hub — RD-048/RD-049). It is deliberately ISOLATED here so the rest of the library
(``canonical.py`` + ``verify.py``) stays PURE stdlib and fully offline-unit-testable;
the fail-closed gate in ``verify.py`` takes the verifier as an injected callable, so
tests use a stub and never import this module.

At runtime in the spoke Lambda, ``cryptography`` is provided by DOCKER-BUNDLING it into
the Lambda asset (the same mechanism the hub_ingest validator uses for
jsonschema/rpds-py — the build sandbox has PyPI blocked, so it cannot be installed or
unit-tested here; the signature path is proven in the LIVE validation instead).

KMS signs ECDSA with a DER-encoded signature (the KMS ``Sign`` output for an
ECC_NIST_P256 key + ``ECDSA_SHA_256`` is ASN.1/DER). ``cryptography``'s
``public_key.verify(signature, data, ec.ECDSA(hashes.SHA256()))`` expects exactly that
DER encoding, so no re-encoding is needed. The public key is a PEM-encoded
SubjectPublicKeyInfo (what ``aws kms get-public-key`` gives, wrapped in PEM).
"""

from __future__ import annotations


def verify_ecdsa_p256_sha256(
    message: bytes, signature_der: bytes, public_key_pem: bytes
) -> bool:
    """Verify a DER-encoded ECDSA-P256/SHA-256 signature over ``message`` against the
    PEM public key. Returns True iff valid; returns False on an invalid signature and
    on ANY error (fail-closed — never raises to the caller). Requires the bundled
    ``cryptography`` package at runtime."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        public_key = load_pem_public_key(public_key_pem)
        try:
            public_key.verify(signature_der, message, ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            return False
    except Exception:  # noqa: BLE001 - fail-closed: any crypto/dep/key error => not verified
        # Missing dependency, malformed key, wrong key type, etc. -> fail-closed.
        return False
