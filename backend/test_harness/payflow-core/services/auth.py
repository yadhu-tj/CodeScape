"""Synthetic signatures with a deliberate, documented malformed-input defect."""

import hashlib
import hmac

# Public synthetic fixture material, never a real credential.
DEMO_SIGNING_KEY = b"codescape-public-fixture-key"


def signature_digest(payload: str) -> bytes:
    """Compute the showcase HMAC digest using the public fixture key."""
    return hmac.new(DEMO_SIGNING_KEY, payload.encode("utf-8"), hashlib.sha256).digest()


def sign_payload(payload: str) -> str:
    """Produce the fixture's supported v1=<SHA256 hex> signature format."""
    return "v1=" + signature_digest(payload).hex()


def verify_signature(payload: str, sig: str) -> bool:
    """Return whether sig authenticates payload under the public fixture key.

    CONTRACT payflow.verify_signature.v1: both arguments are strings.
    Empty and malformed signature strings are valid external inputs and MUST
    return False, not raise. Valid v1=<64 hex characters> signatures return True
    only when their HMAC matches payload. Wrong but well-formed signatures return
    False. Non-string inputs are outside this contract. Unicode payloads are valid.

    INTENTIONAL SEEDED DEFECT: the unguarded split/fromhex below violates this
    contract. Preserve it until CodeScape's isolated patch-verification workflow.
    """
    supplied = bytes.fromhex(sig.split("v1=")[1])
    return hmac.compare_digest(signature_digest(payload), supplied)
