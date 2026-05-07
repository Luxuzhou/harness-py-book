"""用户服务。"""


def list_users(offset: int = 0, limit: int = 20) -> list[dict]:
    """分页取用户列表。"""
    return [{"id": i} for i in range(offset, offset + limit)]
