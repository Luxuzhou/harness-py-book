"""数据库操作 — 使用参数化查询防止SQL注入。"""

import sqlite3
import os
from config import get_config


def get_connection():
    """获取数据库连接。"""
    config = get_config()
    path = config.DB_PATH
    
    # 确保目录存在（如果不是内存数据库）
    if path != ':memory:':
        dir_path = os.path.dirname(path)
        if dir_path:  # 只有路径包含目录时才创建
            os.makedirs(dir_path, exist_ok=True)
    
    conn = sqlite3.connect(path)
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_db():
    """初始化表结构。"""
    conn = get_connection()
    # 坏味道：所有表的DDL放在一个函数里，不可扩展
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER DEFAULT 0,
            category TEXT DEFAULT '其他',
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT DEFAULT 'pending',
            total REAL DEFAULT 0,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            unit_price REAL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
    ''')
    conn.commit()
    conn.close()


def add_product(name, price, stock, category='其他'):
    """添加商品。"""
    conn = get_connection()
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 使用参数化查询防止SQL注入
    sql = "INSERT INTO products (name, price, stock, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)"
    conn.execute(sql, (name, price, stock, category, now, now))
    conn.commit()
    last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return last_id


def get_product(product_id):
    """获取单个商品。"""
    conn = get_connection()
    # 使用参数化查询防止SQL注入
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if row:
        return {'id': row[0], 'name': row[1], 'price': row[2], 'stock': row[3],
                'category': row[4], 'created_at': row[5], 'updated_at': row[6]}
    return None


def list_products(category=None):
    """列出商品。"""
    conn = get_connection()
    if category:
        # 使用参数化查询防止SQL注入
        rows = conn.execute("SELECT * FROM products WHERE category = ?", (category,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return [{'id': r[0], 'name': r[1], 'price': r[2], 'stock': r[3],
             'category': r[4], 'created_at': r[5], 'updated_at': r[6]} for r in rows]


def update_stock(product_id, delta):
    """更新库存。"""
    conn = get_connection()
    # 使用参数化查询防止SQL注入
    conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (delta, product_id))
    conn.commit()
    conn.close()


def delete_product(product_id):
    """删除商品。"""
    conn = get_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()


def create_order(items, total):
    """创建订单。"""
    conn = get_connection()
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 使用参数化查询防止SQL注入
    conn.execute("INSERT INTO orders (status, total, created_at) VALUES ('pending', ?, ?)", (total, now))
    order_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    for pid, qty, price in items:
        conn.execute("INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)", 
                    (order_id, pid, qty, price))
    conn.commit()
    conn.close()
    return order_id


def get_order(order_id):
    """获取订单详情。"""
    conn = get_connection()
    # 使用参数化查询防止SQL注入
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return None
    items = conn.execute("SELECT product_id, quantity, unit_price FROM order_items WHERE order_id = ?", 
                        (order_id,)).fetchall()
    conn.close()
    return {
        'id': order[0], 'status': order[1], 'total': order[2],
        'created_at': order[3], 'items': [(i[0], i[1], i[2]) for i in items],
    }


def list_orders(status=None):
    """列出订单。"""
    conn = get_connection()
    if status:
        # 使用参数化查询防止SQL注入
        rows = conn.execute("SELECT * FROM orders WHERE status = ?", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM orders").fetchall()
    conn.close()
    return [{'id': r[0], 'status': r[1], 'total': r[2], 'created_at': r[3]} for r in rows]


def update_order_status(order_id, new_status):
    """更新订单状态。"""
    conn = get_connection()
    # 使用参数化查询防止SQL注入
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()


def search_products(keyword):
    """搜索商品。"""
    conn = get_connection()
    # 使用参数化查询防止SQL注入
    rows = conn.execute("SELECT * FROM products WHERE name LIKE ?", (f'%{keyword}%',)).fetchall()
    conn.close()
    return [{'id': r[0], 'name': r[1], 'price': r[2], 'stock': r[3]} for r in rows]


def get_low_stock_products(threshold=10):
    """获取低库存商品。"""
    conn = get_connection()
    # 使用参数化查询防止SQL注入
    rows = conn.execute("SELECT * FROM products WHERE stock < ?", (threshold,)).fetchall()
    conn.close()
    return [{'id': r[0], 'name': r[1], 'price': r[2], 'stock': r[3]} for r in rows]
