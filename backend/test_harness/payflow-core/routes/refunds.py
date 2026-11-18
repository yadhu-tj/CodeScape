"""Refund endpoints used to distinguish unrelated impact branches."""

from fastapi import APIRouter
from services.refunds import process_refund, refund_summary

router = APIRouter()


@router.post("/refunds/create")
def refund(payment_id: str, amount_cents: int) -> dict:
    return process_refund(payment_id, amount_cents)


@router.get("/refunds/status")
def refund_status(payment_id: str) -> dict:
    return refund_summary(payment_id)


@router.get("/refunds/list")
def list_refunds() -> list[dict]:
    return []
