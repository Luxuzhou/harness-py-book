"""管理后台。"""
from src.user_service import list_users


def admin_user_list():
    return list_users(offset=0, limit=100)
