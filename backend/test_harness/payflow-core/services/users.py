"""Small synthetic user directory with an additional class-method call."""

from models.user import default_user, user_public

USERS = {"user_demo": default_user()}


def normalize_user_id(user_id: str) -> str:
    value = user_id.strip()
    if not value:
        raise ValueError("User ID must not be empty")
    return value


class UserDirectory:
    def lookup(self, user_id: str) -> dict:
        return USERS[normalize_user_id(user_id)]


def get_user(user_id: str) -> dict:
    return user_public(UserDirectory().lookup(user_id))


def create_user(user_id: str, display_name: str) -> dict:
    key = normalize_user_id(user_id)
    if key in USERS:
        raise ValueError("User already exists")
    USERS[key] = {"id": key, "display_name": display_name, "active": True}
    return user_public(USERS[key])
