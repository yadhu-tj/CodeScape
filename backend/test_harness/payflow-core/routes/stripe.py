"""Webhook entrypoint for the known two-edge reverse-impact chain."""

from fastapi import APIRouter, Body, Header
from services.webhook_listener import handle_webhook

router = APIRouter()


@router.post("/api/v1/stripe")
def stripe_webhook(
    payload: str = Body(..., media_type="text/plain"),
    signature: str = Header(..., alias="Stripe-Signature"),
) -> dict:
    """Forward the original payload text and signature without changing them."""
    return handle_webhook(payload, signature)
