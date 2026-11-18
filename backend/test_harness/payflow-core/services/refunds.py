"""Deterministic refund behavior; never moves actual funds."""

from models.payment import create_payment, payment_public, transition_payment


def validate_refund(payment_id: str, amount_cents: int) -> None:
    if not payment_id or type(amount_cents) is not int or amount_cents <= 0:
        raise ValueError("A payment ID and positive integer amount are required")


def process_refund(payment_id: str, amount_cents: int) -> dict:
    validate_refund(payment_id, amount_cents)
    payment = create_payment(payment_id, amount_cents, "USD")
    return payment_public(transition_payment(payment, "refunded"))


def refund_summary(payment_id: str) -> dict:
    return {"payment_id": payment_id, "persisted_refunds": 0}
