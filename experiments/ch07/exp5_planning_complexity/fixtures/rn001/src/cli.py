"""命令行工具。"""
from src.auth import check_token


def login(token: str) -> str:
    return "ok" if check_token(token) else "denied"
