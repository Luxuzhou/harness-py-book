"""Request middleware. Note: this module is easy to overlook in greps."""
from src.api import fetch_user


def authenticate(uid: int) -> bool:
    """Authenticate by checking user exists."""
    user = fetch_user(uid)
    return user.get("id") == uid


def audit_log(uid: int) -> dict:
    user = fetch_user(uid)
    return {"audited_user": user["name"]}
