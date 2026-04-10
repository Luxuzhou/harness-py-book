"""
库存管理系统主入口 — God Class。
InventoryApp 承载了所有功能：商品管理、订单处理、报表生成、导入导出。
这是一个典型的"上帝类"反模式。
"""

import os
import sys
import json
from datetime import datetime

# 坏味道：相对导入路径操作
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import (init_db, add_product, get_product, list_products,
                       update_stock, delete_product, create_order, get_order,
                       list_orders, update_order_status, search_products,
                       get_low_stock_products)
from models import Product, Order
from utils import (format_price, format_stock_status, format_order_status,
                   format_table, validate_price, validate_stock,
                   validate_product_name, export_products_csv,
                   import_products_csv, export_report_json,
                   calculate_inventory_value, calculate_category_stats,
                   calculate_order_stats, log_action)


class InventoryApp:
    """
    库存管理应用 — God Class。

    职责清单（违反单一职责）：
    1. 商品CRUD
    2. 订单处理
    3. 库存预警
    4. 报表生成
    5. 数据导入导出
    6. 用户交互（CLI菜单）
    """

    def __init__(self):
        from config import get_config
        self.config = get_config()
        self.config.init_dirs()  # 初始化目录
        
        # 从配置获取值
        self.app_name = self.config.APP_NAME
        self.low_stock_threshold = self.config.LOW_STOCK_THRESHOLD
        self.max_order_items = self.config.MAX_ORDER_ITEMS
        self.report_dir = str(self.config.REPORT_DIR)
        self.export_dir = str(self.config.EXPORT_DIR)

        init_db()
        log_action('SYSTEM', f'{self.app_name} 启动')

    # ============ 商品管理 ============

    def add_product(self, name, price, stock, category='其他'):
        """添加商品。"""
        # 坏味道：校验逻辑直接写在这里而不是抽象
        if not validate_product_name(name):
            print(f'ERROR: 无效商品名 "{name}"')
            return None
        if not validate_price(price):
            print(f'ERROR: 无效价格 {price}')
            return None
        if not validate_stock(stock):
            print(f'ERROR: 无效库存 {stock}')
            return None

        product_id = add_product(name, float(price), int(stock), category)
        log_action('ADD_PRODUCT', f'id={product_id} name={name}')
        print(f'商品已添加: {name} (ID: {product_id})')
        return product_id

    def get_product_detail(self, product_id):
        """获取商品详情。"""
        p = get_product(product_id)
        if not p:
            print(f'ERROR: 商品 {product_id} 不存在')
            return None
        return p

    def list_all_products(self, category=None):
        """列出商品。"""
        products = list_products(category)
        if not products:
            print('暂无商品')
            return []

        # 坏味道：表格渲染逻辑在业务方法里
        headers = ['ID', '名称', '价格', '库存', '状态', '分类']
        rows = []
        for p in products:
            rows.append([
                p['id'], p['name'], format_price(p['price']),
                p['stock'], format_stock_status(p['stock']), p.get('category', '')
            ])
        print(format_table(headers, rows))
        return products

    def update_product_stock(self, product_id, delta):
        """更新库存。"""
        p = get_product(product_id)
        if not p:
            print(f'ERROR: 商品 {product_id} 不存在')
            return False

        new_stock = p['stock'] + delta
        if new_stock < 0:
            print(f'ERROR: 库存不足 (当前: {p["stock"]}, 变更: {delta})')
            return False

        update_stock(product_id, delta)
        log_action('UPDATE_STOCK', f'product={product_id} delta={delta} new={new_stock}')

        # 坏味道：预警逻辑散落在各处
        if new_stock < self.low_stock_threshold:
            print(f'⚠ 警告: {p["name"]} 库存偏低 ({new_stock})')

        return True

    def remove_product(self, product_id):
        """删除商品。"""
        p = get_product(product_id)
        if not p:
            print(f'ERROR: 商品 {product_id} 不存在')
            return False

        # 坏味道：没检查是否有未完成的订单引用该商品
        delete_product(product_id)
        log_action('DELETE_PRODUCT', f'id={product_id} name={p["name"]}')
        print(f'商品已删除: {p["name"]}')
        return True

    def search(self, keyword):
        """搜索商品。"""
        results = search_products(keyword)
        if not results:
            print(f'未找到包含 "{keyword}" 的商品')
            return []

        headers = ['ID', '名称', '价格', '库存']
        rows = [[r['id'], r['name'], format_price(r['price']), r['stock']] for r in results]
        print(format_table(headers, rows))
        return results

    # ============ 订单处理 ============

    def create_order(self, items):
        """
        创建订单。
        items: [(product_id, quantity), ...]
        """
        if not items:
            print('ERROR: 订单不能为空')
            return None

        if len(items) > self.max_order_items:
            print(f'ERROR: 订单商品数超过上限 ({self.max_order_items})')
            return None

        order_items = []
        total = 0

        for pid, qty in items:
            p = get_product(pid)
            if not p:
                print(f'ERROR: 商品 {pid} 不存在')
                return None
            if p['stock'] < qty:
                print(f'ERROR: {p["name"]} 库存不足 (需要: {qty}, 实际: {p["stock"]})')
                return None

            order_items.append((pid, qty, p['price']))
            total += qty * p['price']

        # 扣减库存
        for pid, qty in items:
            update_stock(pid, -qty)

        order_id = create_order(order_items, total)
        log_action('CREATE_ORDER', f'id={order_id} total={total} items={len(items)}')
        print(f'订单已创建: #{order_id} 总金额: {format_price(total)}')
        return order_id

    def get_order_detail(self, order_id):
        """获取订单详情。"""
        order = get_order(order_id)
        if not order:
            print(f'ERROR: 订单 {order_id} 不存在')
            return None

        # 坏味道：格式化逻辑在业务方法里
        print(f'\n订单 #{order["id"]}')
        print(f'状态: {format_order_status(order["status"])}')
        print(f'金额: {format_price(order["total"])}')
        print(f'时间: {order["created_at"]}')
        print('商品明细:')
        for pid, qty, price in order['items']:
            p = get_product(pid)
            name = p['name'] if p else f'(已删除:{pid})'
            print(f'  - {name} x{qty} @ {format_price(price)}')

        return order

    def confirm_order(self, order_id):
        """确认订单。"""
        order = get_order(order_id)
        if not order:
            print(f'ERROR: 订单 {order_id} 不存在')
            return False
        # 坏味道：状态机逻辑散落在各方法中
        if order['status'] != 'pending':
            print(f'ERROR: 订单状态不允许确认 (当前: {order["status"]})')
            return False

        update_order_status(order_id, 'confirmed')
        log_action('CONFIRM_ORDER', f'id={order_id}')
        return True

    def ship_order(self, order_id):
        """发货。"""
        order = get_order(order_id)
        if not order:
            return False
        if order['status'] != 'confirmed':
            print(f'ERROR: 未确认的订单不能发货 (当前: {order["status"]})')
            return False
        update_order_status(order_id, 'shipped')
        log_action('SHIP_ORDER', f'id={order_id}')
        return True

    def complete_order(self, order_id):
        """完成订单。"""
        order = get_order(order_id)
        if not order:
            return False
        if order['status'] != 'shipped':
            print(f'ERROR: 未发货的订单不能完成')
            return False
        update_order_status(order_id, 'completed')
        log_action('COMPLETE_ORDER', f'id={order_id}')
        return True

    def cancel_order(self, order_id):
        """取消订单。"""
        order = get_order(order_id)
        if not order:
            return False
        if order['status'] in ('shipped', 'completed'):
            print(f'ERROR: 已发货/已完成的订单不能取消')
            return False

        # 恢复库存
        for pid, qty, _ in order['items']:
            update_stock(pid, qty)

        update_order_status(order_id, 'cancelled')
        log_action('CANCEL_ORDER', f'id={order_id}')
        return True

    def list_all_orders(self, status=None):
        """列出订单。"""
        orders = list_orders(status)
        if not orders:
            print('暂无订单')
            return []
        headers = ['ID', '状态', '金额', '时间']
        rows = [[o['id'], format_order_status(o['status']),
                 format_price(o['total']), o['created_at']] for o in orders]
        print(format_table(headers, rows))
        return orders

    # ============ 报表 ============

    def generate_inventory_report(self):
        """生成库存报表。"""
        products = list_products()
        orders = list_orders()
        low_stock = get_low_stock_products(self.low_stock_threshold)

        report = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'total_products': len(products),
                'total_value': calculate_inventory_value(products),
                'low_stock_count': len(low_stock),
            },
            'category_stats': calculate_category_stats(products),
            'order_stats': calculate_order_stats(orders),
            'low_stock_items': [
                {'id': p['id'], 'name': p['name'], 'stock': p['stock']}
                for p in low_stock
            ],
        }

        # 坏味道：硬编码路径 + 直接打印
        os.makedirs(self.report_dir, exist_ok=True)
        filepath = os.path.join(self.report_dir, f'report_{datetime.now().strftime("%Y%m%d")}.json')
        export_report_json(report, filepath)

        # 打印摘要
        print(f'\n=== 库存报表 ===')
        print(f'商品总数: {report["summary"]["total_products"]}')
        print(f'库存总值: {format_price(report["summary"]["total_value"])}')
        print(f'低库存商品: {report["summary"]["low_stock_count"]} 种')

        if low_stock:
            print('\n低库存预警:')
            for p in low_stock:
                print(f'  ⚠ {p["name"]} — 仅剩 {p["stock"]}')

        if report['order_stats']['count'] > 0:
            stats = report['order_stats']
            print(f'\n订单统计:')
            print(f'  总订单: {stats["count"]}')
            print(f'  总金额: {format_price(stats["total"])}')
            print(f'  均单价: {format_price(stats["avg"])}')

        log_action('GENERATE_REPORT', f'products={len(products)} orders={len(orders)}')
        return report

    def generate_monthly_report(self, year, month):
        """生成月度报表 — 功能不完整，但代码还在。"""
        # 坏味道：半成品代码没清理
        print(f'TODO: 月度报表 {year}-{month:02d} 尚未实现')
        return None

    # ============ 导入导出 ============

    def export_products(self, filepath=None):
        """导出商品到CSV。"""
        products = list_products()
        if not products:
            print('没有可导出的商品')
            return

        if not filepath:
            # 坏味道：硬编码
            os.makedirs(self.export_dir, exist_ok=True)
            filepath = os.path.join(self.export_dir, 'products.csv')

        export_products_csv(products, filepath)
        log_action('EXPORT', f'products to {filepath}')

    def import_products(self, filepath):
        """从CSV导入商品。"""
        items = import_products_csv(filepath)
        if not items:
            print('导入失败或文件为空')
            return 0

        count = 0
        for item in items:
            pid = self.add_product(
                item['name'], item['price'], item['stock'],
                item.get('category', '其他'),
            )
            if pid:
                count += 1

        log_action('IMPORT', f'{count}/{len(items)} products from {filepath}')
        print(f'导入完成: {count}/{len(items)} 条')
        return count

    # ============ CLI菜单 ============

    def run_cli(self):
        """交互式命令行 — 整个UI逻辑混在业务类里。"""
        print(f'\n{"="*40}')
        print(f'  {self.app_name}')
        print(f'{"="*40}')

        while True:
            print('\n--- 主菜单 ---')
            print('1. 商品管理')
            print('2. 订单管理')
            print('3. 报表')
            print('4. 导入/导出')
            print('0. 退出')

            choice = input('\n请选择: ').strip()

            if choice == '1':
                self._product_menu()
            elif choice == '2':
                self._order_menu()
            elif choice == '3':
                self.generate_inventory_report()
            elif choice == '4':
                self._io_menu()
            elif choice == '0':
                print('再见！')
                break
            else:
                print('无效选择')

    def _product_menu(self):
        """商品子菜单。"""
        print('\n--- 商品管理 ---')
        print('1. 添加商品')
        print('2. 查看商品')
        print('3. 搜索商品')
        print('4. 更新库存')
        print('5. 删除商品')
        print('0. 返回')

        c = input('请选择: ').strip()
        if c == '1':
            name = input('商品名: ')
            price = input('价格: ')
            stock = input('库存: ')
            cat = input('分类 (回车默认"其他"): ') or '其他'
            self.add_product(name, price, stock, cat)
        elif c == '2':
            self.list_all_products()
        elif c == '3':
            kw = input('搜索关键词: ')
            self.search(kw)
        elif c == '4':
            pid = input('商品ID: ')
            delta = input('变更数量(正数入库/负数出库): ')
            try:
                self.update_product_stock(int(pid), int(delta))
            except ValueError:
                print('请输入有效数字')
        elif c == '5':
            pid = input('商品ID: ')
            try:
                self.remove_product(int(pid))
            except ValueError:
                print('请输入有效数字')

    def _order_menu(self):
        """订单子菜单。"""
        print('\n--- 订单管理 ---')
        print('1. 创建订单')
        print('2. 查看订单')
        print('3. 所有订单')
        print('4. 确认订单')
        print('5. 发货')
        print('6. 完成订单')
        print('7. 取消订单')
        print('0. 返回')

        c = input('请选择: ').strip()
        if c == '1':
            items = []
            while True:
                pid = input('商品ID (输入空行结束): ').strip()
                if not pid:
                    break
                qty = input('数量: ')
                try:
                    items.append((int(pid), int(qty)))
                except ValueError:
                    print('请输入有效数字')
            if items:
                self.create_order(items)
        elif c == '2':
            oid = input('订单ID: ')
            try:
                self.get_order_detail(int(oid))
            except ValueError:
                print('请输入有效数字')
        elif c == '3':
            self.list_all_orders()
        elif c == '4':
            oid = input('订单ID: ')
            try:
                self.confirm_order(int(oid))
            except ValueError:
                print('请输入有效数字')
        elif c == '5':
            oid = input('订单ID: ')
            try:
                self.ship_order(int(oid))
            except ValueError:
                print('请输入有效数字')
        elif c == '6':
            oid = input('订单ID: ')
            try:
                self.complete_order(int(oid))
            except ValueError:
                print('请输入有效数字')
        elif c == '7':
            oid = input('订单ID: ')
            try:
                self.cancel_order(int(oid))
            except ValueError:
                print('请输入有效数字')

    def _io_menu(self):
        """导入导出子菜单。"""
        print('\n--- 导入/导出 ---')
        print('1. 导出商品CSV')
        print('2. 导入商品CSV')
        print('0. 返回')

        c = input('请选择: ').strip()
        if c == '1':
            self.export_products()
        elif c == '2':
            fp = input('CSV文件路径: ')
            self.import_products(fp)


# 坏味道：模块级可执行代码
if __name__ == '__main__':
    app = InventoryApp()
    if len(sys.argv) > 1 and sys.argv[1] == '--report':
        app.generate_inventory_report()
    else:
        app.run_cli()
