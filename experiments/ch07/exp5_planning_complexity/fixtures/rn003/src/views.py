"""前端视图。"""
from src.user_service import list_users


def users_page(page: int = 0):
    return list_users(offset=page * 20, limit=20)
