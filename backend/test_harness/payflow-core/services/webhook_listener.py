"""Direct verifier caller plus a separate dynamic-dispatch branch."""

import json
from services.auth import verify_signature
from services.dispatcher import dispatch_event


def parse_payload(payload: str) -> dict:
    event = json.loads(payload)
    if not isinstance(event, dict):
        raise ValueError("Webhook payload must be a JSON object")
    return event


def handle_webhook(payload: str, sig: str) -> dict:
    """Reject unauthenticated payloads, then dispatch the authenticated event."""
    if not verify_signature(payload, sig):
        return {"accepted": False, "reason": "invalid_signature"}
    event = parse_payload(payload)
    return {"accepted": True, "result": dispatch_event(event["type"], event)}


def webhook_summary(event: dict) -> dict:
    return {"type": event.get("type", "unknown"), "id": event.get("id", "missing")}
