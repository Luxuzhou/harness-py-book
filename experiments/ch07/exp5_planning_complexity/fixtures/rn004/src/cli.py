"""Command-line entry."""
from src.api import fetch_user, fetch_post, fetch_comment


def render_user(uid: int) -> str:
    user = fetch_user(uid)
    return f'user: {user["name"]}'


def render_post(pid: int) -> str:
    post = fetch_post(pid)
    return f'post: {post["title"]}'


def render_comment(cid: int) -> str:
    comment = fetch_comment(cid)
    return f'comment: {comment["body"]}'
