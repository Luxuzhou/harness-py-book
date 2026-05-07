"""业务服务层。"""
from src.db import query_one


def latest_login(uid: int):
    return query_one("SELECT MAX(ts) FROM logins WHERE uid=%s", (uid,))
