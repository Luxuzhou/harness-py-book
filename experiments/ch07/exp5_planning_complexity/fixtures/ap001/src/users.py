"""用户管理。"""


def get_user(uid: int) -> dict | None:
    """从数据库按 ID 查用户。"""
    # 这里假装调数据库
    return {"id": uid, "name": f"user_{uid}", "deleted": False}
