"""认证中间件。"""
from src.auth import check_token


def auth_middleware(request: dict) -> bool:
    return check_token(request.get("token", ""))
