"""仓储层。"""
from src.db import query_one


def get_user(uid: int):
    return query_one("SELECT * FROM users WHERE id=%s", (uid,))


def get_order(oid: int):
    return query_one("SELECT * FROM orders WHERE id=%s", (oid,))
