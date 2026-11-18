"""A bounded mutual call cycle for static traversal, not runaway execution."""

from utils.audit import audit_and_retry


def backoff_seconds(attempt: int) -> int:
    return min(2 ** max(0, attempt), 32)


def is_retryable(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


def retry_with_audit(remaining: int, events: list[str] | None = None) -> list[str]:
    """Decrement remaining on every step so the actual execution terminates."""
    if remaining < 0 or remaining > 16:
        raise ValueError("Retry budget must be between zero and sixteen")
    if events is None:
        events = []
    if remaining == 0:
        return events
    events.append("retry")
    return audit_and_retry(remaining - 1, events)
