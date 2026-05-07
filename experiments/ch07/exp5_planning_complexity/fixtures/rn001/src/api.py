"""API 入口。"""
from src.auth import check_token


def authorize(request: dict) -> bool:
    if not check_token(request.get("token", "")):
        return False
    return True
