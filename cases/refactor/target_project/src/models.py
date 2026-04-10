"""数据模型 — 但混入了不该有的业务逻辑。"""

import json
from datetime import datetime


class Product:
    """商品。"""
    def __init__(self, id, name, price, stock, category='其他'):
        self.id = id
        self.name = name
        self.price = price
        self.stock = stock
        self.category = category
        self.created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.updated_at = self.created_at

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'price': self.price,
            'stock': self.stock, 'category': self.category,
            'created_at': self.created_at, 'updated_at': self.updated_at,
        }

    # 坏味道：业务逻辑混入模型
    def apply_discount(self, percent):
        """打折 — 这不该在Model里。"""
        if percent < 0 or percent > 100:
            print(f'ERROR: 无效折扣 {percent}')
            return False
        self.price = round(self.price * (1 - percent / 100), 2)
        self.updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return True

    # 坏味道：格式化逻辑混入模型
    def format_label(self):
        """生成价签标签 — 这该是展示层的事。"""
        if self.stock == 0:
            status = '【缺货】'
        elif self.stock < 10:
            status = '【低库存】'
        else:
            status = ''
        return f'{status}{self.name} ¥{self.price:.2f} (库存:{self.stock})'

    # 坏味道：序列化逻辑混入模型
    def to_csv_line(self):
        return f'{self.id},{self.name},{self.price},{self.stock},{self.category}'


class Order:
    """订单。"""
    def __init__(self, id, items=None, status='pending'):
        self.id = id
        self.items = items or []  # [(product_id, quantity, unit_price)]
        self.status = status
        self.created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def total(self):
        return sum(qty * price for _, qty, price in self.items)

    def to_dict(self):
        return {
            'id': self.id, 'items': self.items, 'status': self.status,
            'total': self.total(), 'created_at': self.created_at,
        }

    # 坏味道：验证逻辑混入模型
    def validate(self):
        """验证订单有效性 — 这该在Service层做。"""
        errors = []
        if not self.items:
            errors.append('订单不能为空')
        for pid, qty, price in self.items:
            if qty <= 0:
                errors.append(f'商品{pid}数量必须>0')
            if price < 0:
                errors.append(f'商品{pid}价格不能为负')
        return errors

    # 坏味道：直接操作JSON文件
    def save_to_file(self, filepath='orders.json'):
        """持久化 — 模型不该知道存储细节。"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = []
        data.append(self.to_dict())
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
