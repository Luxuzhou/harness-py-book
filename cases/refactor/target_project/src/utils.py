"""工具函数 — 职责混乱：格式化+校验+IO+统计全混一起。"""

import json
import csv
import os
from datetime import datetime


# ============ 格式化函数 ============

def format_price(price):
    """格式化价格显示。"""
    if price >= 10000:
        return f'¥{price/10000:.1f}万'
    return f'¥{price:.2f}'


def format_stock_status(stock):
    """格式化库存状态。"""
    if stock == 0:
        return '缺货'
    elif stock < 5:
        return '紧急'
    elif stock < 20:
        return '偏低'
    else:
        return '充足'


def format_order_status(status):
    """中文状态。"""
    from config import get_config
    config = get_config()
    return config.ORDER_STATUS_MAPPING.get(status, status)


def format_table(headers, rows, widths=None):
    """格式化表格输出。"""
    if not widths:
        widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=4)) + 2
                  for i, h in enumerate(headers)]
    # 坏味道：复杂的格式化逻辑散落在工具模块
    line = '+' + '+'.join('-' * w for w in widths) + '+'
    header = '|' + '|'.join(str(h).center(w) for h, w in zip(headers, widths)) + '|'
    result = [line, header, line]
    for row in rows:
        r = '|' + '|'.join(str(row[i]).center(w) for i, w in enumerate(widths)) + '|'
        result.append(r)
    result.append(line)
    return '\n'.join(result)


# ============ 校验函数 ============

def validate_price(price):
    """校验价格。"""
    try:
        p = float(price)
        return p > 0
    except (ValueError, TypeError):
        return False


def validate_stock(stock):
    """校验库存数量。"""
    try:
        s = int(stock)
        return s >= 0
    except (ValueError, TypeError):
        return False


def validate_product_name(name):
    """校验商品名。"""
    from config import get_config
    config = get_config()
    
    if not name or not name.strip():
        return False
    if len(name) > config.MAX_PRODUCT_NAME_LENGTH:
        return False
    
    return name.lower() not in config.BANNED_PRODUCT_NAMES


# ============ IO函数 ============

def export_products_csv(products, filepath='products_export.csv'):
    """导出商品到CSV。"""
    # 坏味道：硬编码默认路径
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', '名称', '价格', '库存', '分类'])
        for p in products:
            writer.writerow([p['id'], p['name'], p['price'], p['stock'], p.get('category', '')])
    print(f'已导出 {len(products)} 条商品到 {filepath}')


def import_products_csv(filepath):
    """从CSV导入商品。"""
    if not os.path.exists(filepath):
        print(f'ERROR: 文件不存在 {filepath}')
        return []
    products = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append({
                'name': row.get('名称', row.get('name', '')),
                'price': float(row.get('价格', row.get('price', 0))),
                'stock': int(row.get('库存', row.get('stock', 0))),
                'category': row.get('分类', row.get('category', '其他')),
            })
    return products


def export_report_json(data, filepath='report.json'):
    """导出报告为JSON。"""
    # 坏味道：硬编码路径
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'报告已保存到 {filepath}')


def load_config(filepath='config.json'):
    """加载配置 — 但到处都没用这个函数。"""
    # 坏味道：死代码
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# ============ 统计函数 ============

def calculate_inventory_value(products):
    """计算库存总价值。"""
    return sum(p['price'] * p['stock'] for p in products)


def calculate_category_stats(products):
    """按分类统计。"""
    stats = {}
    for p in products:
        cat = p.get('category', '其他')
        if cat not in stats:
            stats[cat] = {'count': 0, 'total_stock': 0, 'total_value': 0}
        stats[cat]['count'] += 1
        stats[cat]['total_stock'] += p['stock']
        stats[cat]['total_value'] += p['price'] * p['stock']
    return stats


def calculate_order_stats(orders):
    """订单统计。"""
    if not orders:
        return {'count': 0, 'total': 0, 'avg': 0}
    total = sum(o.get('total', 0) for o in orders)
    return {
        'count': len(orders),
        'total': round(total, 2),
        'avg': round(total / len(orders), 2),
        'by_status': _group_by_status(orders),
    }


def _group_by_status(orders):
    """按状态分组。"""
    groups = {}
    for o in orders:
        s = o.get('status', 'unknown')
        groups[s] = groups.get(s, 0) + 1
    return groups


# ============ 混入的日志函数 ============

def log_action(action, detail=''):
    """记录操作日志。"""
    from config import get_config
    config = get_config()
    config.init_dirs()  # 确保日志目录存在
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{timestamp}] {action}: {detail}\n'
    with open(config.LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line)
