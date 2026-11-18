"""Dynamic registry deliberately leaves handler(payload) unresolved statically."""


def payment_completed(payload: dict) -> dict:
    return {"status": "completed", "event_id": payload.get("id", "unknown")}


def payment_failed(payload: dict) -> dict:
    return {"status": "failed", "event_id": payload.get("id", "unknown")}


EVENT_REGISTRY = {
    "payment.completed": payment_completed,
    "payment.failed": payment_failed,
}


def register_handler(event_type: str, callback) -> None:
    if not callable(callback):
        raise TypeError("Handler must be callable")
    EVENT_REGISTRY[event_type] = callback


def dispatch_event(event_type: str, payload: dict) -> dict:
    """Look up the callback at runtime; no external service is contacted."""
    handler = EVENT_REGISTRY[event_type]
    return handler(payload)
