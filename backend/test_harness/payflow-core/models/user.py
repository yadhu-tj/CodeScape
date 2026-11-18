"""Public synthetic user records."""


def default_user() -> dict:
    return {"id": "user_demo", "display_name": "Demo User", "active": True}


def user_public(user: dict) -> dict:
    return {key: user[key] for key in ("id", "display_name", "active")}


def user_exists(user_id: str, users: dict) -> bool:
    return user_id in users
