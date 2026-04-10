"""
库存管理系统单元测试 - 补充现有功能的测试
目标：覆盖率达到60%以上
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime

# 设置临时数据库
_tmpdir = tempfile.mkdtemp()
os.environ['INVENTORY_DB'] = os.path.join(_tmpdir, 'test.db')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import (
    init_db, add_product, get_product, list_products, update_stock,
    delete_product, create_order, get_order, list_orders, update_order_status,
    search_products, get_low_stock_products
)
from utils import (
    format_price, format_stock_status, format_order_status, format_table,
    validate_price, validate_stock, validate_product_name,
    calculate_inventory_value, calculate_category_stats, calculate_order_stats,
    log_action
)
from models import Product, Order


class TestDatabaseOperations(unittest.TestCase):
    """数据库操作测试"""
    
    @classmethod
    def setUpClass(cls):
        init_db()
    
    def setUp(self):
        # 清空数据 - 使用数据库模块的函数
        from database import get_connection
        conn = get_connection()
        conn.execute("DELETE FROM products")
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM order_items")
        conn.commit()
        conn.close()
    
    def test_add_and_get_product(self):
        """测试添加和获取商品"""
        pid = add_product('测试商品', 29.99, 100, '电子产品')
        self.assertIsNotNone(pid)
        
        product = get_product(pid)
        self.assertEqual(product['name'], '测试商品')
        self.assertEqual(product['price'], 29.99)
        self.assertEqual(product['stock'], 100)
        self.assertEqual(product['category'], '电子产品')
    
    def test_list_products(self):
        """测试列出商品"""
        # 添加几个商品
        add_product('商品A', 10.0, 5, '分类1')
        add_product('商品B', 20.0, 10, '分类2')
        
        products = list_products()
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0]['name'], '商品A')
        self.assertEqual(products[1]['name'], '商品B')
    
    def test_list_products_by_category(self):
        """测试按分类列出商品"""
        add_product('商品A', 10.0, 5, '分类1')
        add_product('商品B', 20.0, 10, '分类2')
        add_product('商品C', 30.0, 15, '分类1')
        
        products = list_products('分类1')
        self.assertEqual(len(products), 2)
        for p in products:
            self.assertEqual(p['category'], '分类1')
    
    def test_update_stock(self):
        """测试更新库存"""
        pid = add_product('测试商品', 10.0, 100)
        
        # 增加库存
        update_stock(pid, 50)
        product = get_product(pid)
        self.assertEqual(product['stock'], 150)
        
        # 减少库存
        update_stock(pid, -30)
        product = get_product(pid)
        self.assertEqual(product['stock'], 120)
    
    def test_delete_product(self):
        """测试删除商品"""
        pid = add_product('测试商品', 10.0, 100)
        
        # 确认商品存在
        product = get_product(pid)
        self.assertIsNotNone(product)
        
        # 删除商品
        delete_product(pid)
        
        # 确认商品已删除
        product = get_product(pid)
        self.assertIsNone(product)
    
    def test_create_and_get_order(self):
        """测试创建和获取订单"""
        # 添加商品
        pid1 = add_product('商品A', 10.0, 100)
        pid2 = add_product('商品B', 20.0, 50)
        
        # 创建订单
        items = [(pid1, 2, 10.0), (pid2, 3, 20.0)]
        total = 2*10.0 + 3*20.0
        order_id = create_order(items, total)
        
        # 获取订单
        order = get_order(order_id)
        self.assertIsNotNone(order)
        self.assertEqual(order['status'], 'pending')
        self.assertEqual(order['total'], total)
        self.assertEqual(len(order['items']), 2)
    
    def test_list_orders(self):
        """测试列出订单"""
        # 创建几个订单
        pid = add_product('测试商品', 10.0, 100)
        items = [(pid, 2, 10.0)]
        
        create_order(items, 20.0)
        create_order(items, 20.0)
        
        orders = list_orders()
        self.assertEqual(len(orders), 2)
    
    def test_update_order_status(self):
        """测试更新订单状态"""
        pid = add_product('测试商品', 10.0, 100)
        items = [(pid, 2, 10.0)]
        order_id = create_order(items, 20.0)
        
        # 更新状态
        update_order_status(order_id, 'confirmed')
        
        order = get_order(order_id)
        self.assertEqual(order['status'], 'confirmed')
    
    def test_search_products(self):
        """测试搜索商品"""
        add_product('苹果手机', 5999.0, 50, '手机')
        add_product('苹果电脑', 12999.0, 30, '电脑')
        add_product('华为手机', 3999.0, 100, '手机')
        
        results = search_products('苹果')
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIn('苹果', r['name'])
    
    def test_get_low_stock_products(self):
        """测试获取低库存商品"""
        add_product('商品A', 10.0, 5)   # 低库存
        add_product('商品B', 20.0, 15)  # 正常库存
        add_product('商品C', 30.0, 3)   # 低库存
        
        low_stock = get_low_stock_products(threshold=10)
        self.assertEqual(len(low_stock), 2)
        for p in low_stock:
            self.assertLess(p['stock'], 10)


class TestUtilsFunctions(unittest.TestCase):
    """工具函数测试"""
    
    def test_format_price(self):
        """测试价格格式化"""
        self.assertEqual(format_price(9.9), '¥9.90')
        self.assertEqual(format_price(100), '¥100.00')
        self.assertEqual(format_price(15000), '¥1.5万')
        self.assertEqual(format_price(123456), '¥12.3万')
    
    def test_format_stock_status(self):
        """测试库存状态格式化"""
        self.assertEqual(format_stock_status(0), '缺货')
        self.assertEqual(format_stock_status(3), '紧急')
        self.assertEqual(format_stock_status(10), '偏低')
        self.assertEqual(format_stock_status(50), '充足')
    
    def test_format_order_status(self):
        """测试订单状态格式化"""
        self.assertEqual(format_order_status('pending'), '待处理')
        self.assertEqual(format_order_status('confirmed'), '已确认')
        self.assertEqual(format_order_status('shipped'), '已发货')
        self.assertEqual(format_order_status('completed'), '已完成')
        self.assertEqual(format_order_status('cancelled'), '已取消')
        self.assertEqual(format_order_status('unknown'), 'unknown')
    
    def test_format_table(self):
        """测试表格格式化"""
        headers = ['ID', 'Name']
        rows = [[1, 'Alice'], [2, 'Bob']]
        table = format_table(headers, rows)
        
        self.assertIn('ID', table)
        self.assertIn('Name', table)
        self.assertIn('Alice', table)
        self.assertIn('Bob', table)
    
    def test_validate_price(self):
        """测试价格验证"""
        self.assertTrue(validate_price(10))
        self.assertTrue(validate_price(10.5))
        self.assertTrue(validate_price('10.5'))
        self.assertFalse(validate_price(-1))
        self.assertFalse(validate_price(0))
        self.assertFalse(validate_price('abc'))
        self.assertFalse(validate_price(None))
    
    def test_validate_stock(self):
        """测试库存验证"""
        self.assertTrue(validate_stock(0))
        self.assertTrue(validate_stock(10))
        self.assertTrue(validate_stock('10'))
        self.assertFalse(validate_stock(-1))
        self.assertFalse(validate_stock('abc'))
        self.assertFalse(validate_stock(None))
    
    def test_validate_product_name(self):
        """测试商品名验证"""
        self.assertTrue(validate_product_name('正常商品名'))
        self.assertTrue(validate_product_name('Product 123'))
        self.assertFalse(validate_product_name(''))
        self.assertFalse(validate_product_name('   '))
        self.assertFalse(validate_product_name('测试'))  # 禁用词
        self.assertFalse(validate_product_name('test'))  # 禁用词
    
    def test_calculate_inventory_value(self):
        """测试库存价值计算"""
        products = [
            {'price': 10.0, 'stock': 5},
            {'price': 20.0, 'stock': 3},
            {'price': 15.0, 'stock': 2},
        ]
        total = calculate_inventory_value(products)
        self.assertEqual(total, 10.0*5 + 20.0*3 + 15.0*2)
    
    def test_calculate_category_stats(self):
        """测试分类统计"""
        products = [
            {'category': 'A', 'price': 10.0, 'stock': 5},
            {'category': 'B', 'price': 20.0, 'stock': 3},
            {'category': 'A', 'price': 15.0, 'stock': 2},
        ]
        stats = calculate_category_stats(products)
        
        self.assertEqual(stats['A']['count'], 2)
        self.assertEqual(stats['A']['total_stock'], 7)
        self.assertEqual(stats['A']['total_value'], 10.0*5 + 15.0*2)
        
        self.assertEqual(stats['B']['count'], 1)
        self.assertEqual(stats['B']['total_stock'], 3)
        self.assertEqual(stats['B']['total_value'], 20.0*3)
    
    def test_calculate_order_stats(self):
        """测试订单统计"""
        orders = [
            {'total': 100.0, 'status': 'pending'},
            {'total': 200.0, 'status': 'confirmed'},
            {'total': 150.0, 'status': 'pending'},
        ]
        stats = calculate_order_stats(orders)
        
        self.assertEqual(stats['count'], 3)
        self.assertEqual(stats['total'], 450.0)
        self.assertEqual(stats['avg'], 150.0)
        self.assertEqual(stats['by_status']['pending'], 2)
        self.assertEqual(stats['by_status']['confirmed'], 1)
    
    def test_calculate_order_stats_empty(self):
        """测试空订单统计"""
        stats = calculate_order_stats([])
        self.assertEqual(stats['count'], 0)
        self.assertEqual(stats['total'], 0)
        self.assertEqual(stats['avg'], 0)


class TestModels(unittest.TestCase):
    """模型测试"""
    
    def test_product_to_dict(self):
        """测试Product转字典"""
        product = Product(1, '测试商品', 29.99, 100, '电子产品')
        data = product.to_dict()
        
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['name'], '测试商品')
        self.assertEqual(data['price'], 29.99)
        self.assertEqual(data['stock'], 100)
        self.assertEqual(data['category'], '电子产品')
        self.assertIn('created_at', data)
        self.assertIn('updated_at', data)
    
    def test_product_apply_discount(self):
        """测试商品打折"""
        product = Product(1, '测试商品', 100.0, 10)
        
        # 有效折扣
        result = product.apply_discount(20)  # 8折
        self.assertTrue(result)
        self.assertEqual(product.price, 80.0)
        
        # 无效折扣
        result = product.apply_discount(120)
        self.assertFalse(result)
        result = product.apply_discount(-10)
        self.assertFalse(result)
    
    def test_product_format_label(self):
        """测试商品标签格式化"""
        # 正常库存
        product = Product(1, '测试商品', 29.99, 50)
        label = product.format_label()
        self.assertIn('测试商品', label)
        self.assertIn('¥29.99', label)
        self.assertIn('库存:50', label)
        
        # 低库存
        product.stock = 5
        label = product.format_label()
        self.assertIn('【低库存】', label)
        
        # 缺货
        product.stock = 0
        label = product.format_label()
        self.assertIn('【缺货】', label)
    
    def test_product_to_csv_line(self):
        """测试商品转CSV行"""
        product = Product(1, '测试商品', 29.99, 100, '电子产品')
        csv_line = product.to_csv_line()
        self.assertEqual(csv_line, '1,测试商品,29.99,100,电子产品')
    
    def test_order_total(self):
        """测试订单总价计算"""
        items = [(1, 2, 10.0), (2, 3, 20.0)]
        order = Order(1, items)
        
        total = order.total()
        self.assertEqual(total, 2*10.0 + 3*20.0)
    
    def test_order_to_dict(self):
        """测试Order转字典"""
        items = [(1, 2, 10.0)]
        order = Order(1, items, 'pending')
        data = order.to_dict()
        
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['status'], 'pending')
        self.assertEqual(data['total'], 20.0)
        self.assertEqual(data['items'], items)
        self.assertIn('created_at', data)
    
    def test_order_validate(self):
        """测试订单验证"""
        # 有效订单
        order = Order(1, [(1, 2, 10.0), (2, 1, 20.0)])
        errors = order.validate()
        self.assertEqual(len(errors), 0)
        
        # 空订单
        order = Order(2, [])
        errors = order.validate()
        self.assertIn('订单不能为空', errors)
        
        # 数量为0
        order = Order(3, [(1, 0, 10.0)])
        errors = order.validate()
        self.assertIn('商品1数量必须>0', errors)
        
        # 价格为负
        order = Order(4, [(1, 2, -10.0)])
        errors = order.validate()
        self.assertIn('商品1价格不能为负', errors)


# 需要导入sqlite3用于测试
import sqlite3

if __name__ == '__main__':
    unittest.main()