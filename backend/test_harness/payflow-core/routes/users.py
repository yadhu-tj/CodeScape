"""User entrypoints with no persistence or external network calls."""

from fastapi import APIRouter
from services.users import create_user, get_user

router = APIRouter()


@router.get("/user/profile")
def profile(user_id: str = "user_demo") -> dict:
    return get_user(user_id)


@router.post("/user/create")
def add_user(user_id: str, display_name: str) -> dict:
    return create_user(user_id, display_name)


@router.get("/user/status")
def user_status() -> dict:
    return {"storage": "in-memory", "synthetic": True}
