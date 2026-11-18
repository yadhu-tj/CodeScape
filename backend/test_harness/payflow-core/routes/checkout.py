"""Checkout routes backed by deterministic in-memory services."""

from fastapi import APIRouter
from services.checkout import CheckoutService, checkout_total

router = APIRouter()


@router.post("/checkout/charge")
def charge(items: list[dict], currency: str = "USD") -> dict:
    return CheckoutService().charge(items, currency)


@router.post("/checkout/quote")
def quote(items: list[dict]) -> dict:
    return {"total_cents": checkout_total(items)}


@router.get("/checkout/status")
def checkout_status() -> dict:
    return {"available": True, "external_gateway": False}
