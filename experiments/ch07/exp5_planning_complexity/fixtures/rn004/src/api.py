"""Public API surface for fetching domain entities."""


def fetch_user(user_id: int) -> dict:
    """Return mock user record."""
    return {"id": user_id, "name": f"user_{user_id}"}


def fetch_post(post_id: int) -> dict:
    """Return mock post record."""
    return {"id": post_id, "title": f"post_{post_id}"}


def fetch_comment(comment_id: int) -> dict:
    """Return mock comment record."""
    return {"id": comment_id, "body": f"comment_{comment_id}"}
