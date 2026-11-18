"""Exactly four clean baseline tests; malformed signatures belong outside this suite."""

from routes.users import profile
from services.auth import sign_payload, verify_signature
from services.checkout import CheckoutService


def test_valid_signature() -> None:
    payload = '{"type":"payment.completed","id":"evt_demo"}'
    assert verify_signature(payload, sign_payload(payload)) is True


def test_wrong_well_formed_signature() -> None:
    assert verify_signature("payload", "v1=" + "00" * 32) is False


def test_checkout_calculation() -> None:
    result = CheckoutService().charge([
        {"price_cents": 1250, "quantity": 2},
        {"price_cents": 500, "quantity": 1},
    ])
    assert result == {"id": "pay_demo", "amount_cents": 3000, "currency": "USD", "status": "authorized"}


def test_user_profile_lookup() -> None:
    assert profile("user_demo") == {"id": "user_demo", "display_name": "Demo User", "active": True}
