"""Simple payment records, intentionally avoiding a database dependency."""


def create_payment(payment_id: str, amount_cents: int, currency: str) -> dict:
    return {"id": payment_id, "amount_cents": amount_cents, "currency": currency, "status": "authorized"}


def payment_public(payment: dict) -> dict:
    return {key: payment[key] for key in ("id", "amount_cents", "currency", "status")}


def transition_payment(payment: dict, status: str) -> dict:
    if status not in {"authorized", "captured", "refunded"}:
        raise ValueError("Unsupported payment state")
    return {**payment, "status": status}
