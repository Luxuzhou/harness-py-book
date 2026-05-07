"""HTTP-style handlers."""
from src.api import fetch_user, fetch_post


def handle_user_request(uid: int):
    return fetch_user(uid)


def handle_post_request(pid: int):
    return fetch_post(pid)
