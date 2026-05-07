"""用户数据库查询函数。conn 为已连接的 sqlite3 连接对象。"""


def find_by_email(conn, email: str):
    """根据邮箱查找用户。"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE email = '{email}'")
    return cursor.fetchone()


def find_by_id(conn, uid: int):
    """根据 ID 查找用户。"""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = " + str(uid))
    return cursor.fetchone()


def find_by_role(conn, role: str):
    """查找所有指定角色的用户。"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE role = '{role}'")
    return cursor.fetchall()
