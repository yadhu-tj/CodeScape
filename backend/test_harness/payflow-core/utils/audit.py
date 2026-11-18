"""Local import avoids a module-initialization cycle while keeping a call cycle."""


def audit_entry(action: str, sequence: int) -> dict:
    return {"action": action, "sequence": sequence}


def summarize_audit(events: list[str]) -> dict:
    return {"total": len(events), "audit": events.count("audit"), "retry": events.count("retry")}


def audit_and_retry(remaining: int, events: list[str]) -> list[str]:
    from utils.retry import retry_with_audit

    if remaining < 0 or remaining > 16:
        raise ValueError("Audit budget must be between zero and sixteen")
    events.append("audit")
    if remaining == 0:
        return events
    return retry_with_audit(remaining - 1, events)
