"""Sandbox-only integration smoke checks, separate from the four-test baseline."""

import json
import os
from pathlib import Path


def main() -> None:
    if not Path("/.dockerenv").exists() or not Path("/workspace/repo/app.py").is_file():
        raise SystemExit("Run this showcase smoke check only inside the prepared Docker sandbox")
    from fastapi.testclient import TestClient
    from app import app
    from services.auth import sign_payload
    from services.dispatcher import dispatch_event
    from utils.retry import retry_with_audit

    assert os.getuid() == 1000 and os.getgid() == 1000
    assert os.statvfs("/workspace/repo").f_flag & os.ST_RDONLY
    assert os.statvfs("/").f_flag & os.ST_RDONLY
    Path("/tmp/codescape-smoke").write_text("writable tmpfs", encoding="utf-8")
    expected_routes = {"/health", "/api/v1/stripe", "/checkout/charge", "/checkout/quote", "/checkout/status", "/user/profile", "/user/create", "/user/status", "/refunds/create", "/refunds/status", "/refunds/list"}
    assert expected_routes <= {route.path for route in app.routes}
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    payload = '{"type":"payment.completed","id":"evt_smoke"}'
    response = client.post("/api/v1/stripe", content=payload, headers={"Content-Type": "text/plain", "Stripe-Signature": sign_payload(payload)})
    assert response.status_code == 200, response.text
    assert response.json() == {"accepted": True, "result": {"status": "completed", "event_id": "evt_smoke"}}
    assert client.post("/checkout/quote", json=[{"price_cents": 100, "quantity": 2}]).json() == {"total_cents": 200}
    assert client.get("/user/profile").json()["id"] == "user_demo"
    assert client.post("/refunds/create", params={"payment_id": "pay_demo", "amount_cents": 100}).json()["status"] == "refunded"
    assert dispatch_event("payment.failed", {"id": "evt_failure"})["status"] == "failed"
    assert retry_with_audit(0) == []
    assert retry_with_audit(3) == ["retry", "audit", "retry", "audit"]
    assert len(retry_with_audit(16)) == 16
    print(json.dumps({"status": "passed", "application_routes": 11, "webhook_chain": "passed", "dispatcher": "passed", "bounded_call_cycle": "passed", "non_root": True, "repo_and_root_readonly": True, "tmpfs_writable": True}))


if __name__ == "__main__":
    main()
