"""Reviewed showcase oracle. Execute only in the isolated Docker sandbox.

The malformed-input test is intentionally RED on the seeded source. It is not
part of payflow-core/tests and must not be counted as a clean baseline failure.
"""

import hashlib
import hmac

import pytest
from services.auth import verify_signature

CONTRACT_ID = "payflow.verify_signature.v1"
PUBLIC_FIXTURE_KEY = b"codescape-public-fixture-key"


def valid_input(payload, sig) -> bool:
    """Explicit contract domain, independently of target annotations."""
    return isinstance(payload, str) and isinstance(sig, str)


@pytest.mark.parametrize("sig", ["", "v1=not-hex", "v1=0"])
def test_malformed_signatures_return_false(sig: str) -> None:
    payload = '{"type":"payment.completed","id":"evt_contract"}'
    assert valid_input(payload, sig)
    assert verify_signature(payload, sig) is False


def test_valid_signature_control() -> None:
    payload = "Unicode payload: नमस्ते"
    digest = hmac.new(PUBLIC_FIXTURE_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    assert verify_signature(payload, "v1=" + digest) is True


def test_wrong_signature_control() -> None:
    assert verify_signature("contract payload", "v1=" + "00" * 32) is False


def test_empty_hex_signature_control() -> None:
    assert verify_signature("contract payload", "v1=") is False


def test_out_of_contract_input_control() -> None:
    # Do not call the target with these inputs and then claim a defect.
    assert valid_input(None, "v1=00") is False
    assert valid_input("payload", None) is False

