"""Synthetic payment authorization with no SDK or gateway side effects."""

from models.payment import create_payment, payment_public


def validate_currency(currency: str) -> str:
    if currency not in {"USD", "INR", "EUR"}:
        raise ValueError("Unsupported showcase currency")
    return currency


def authorize_payment(amount_cents: int, currency: str = "USD") -> dict:
    validate_currency(currency)
    if type(amount_cents) is not int or amount_cents <= 0:
        raise ValueError("Amount must be a positive integer")
    return payment_public(create_payment("pay_demo", amount_cents, currency))


def payment_receipt(payment: dict) -> str:
    return f"{payment['id']}:{payment['amount_cents']}:{payment['currency']}"
