"""Synthetic showcase application; not a production payment service."""

from fastapi import FastAPI
from routes import checkout, refunds, stripe, users

app = FastAPI(title="payflow-core", version="0.1.0")
app.include_router(stripe.router)
app.include_router(checkout.router)
app.include_router(users.router)
app.include_router(refunds.router)


@app.get("/health")
def health_check() -> dict:
    """Expose a simple, statically detectable entrypoint."""
    return {"status": "ok", "mode": "synthetic-showcase"}
