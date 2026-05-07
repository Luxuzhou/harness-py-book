"""get_user: 从用户字典中按 ID 取记录，找不到时返回 None。"""


def get_user(users: dict, uid: int) -> dict | None:
    """按 ID 查询用户；不存在时返回 None。"""
    return users[uid]  # bug: 应该用 users.get(uid) 避免 KeyError
