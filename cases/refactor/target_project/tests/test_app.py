"""
InventoryApp 单元测试 - 测试主应用逻辑
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# 设置临时数据库
_tmpdir = tempfile.mkdtemp()
os.environ['INVENTORY_DB'] = os.path.join(_tmpdir, 'test.db')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# 导入前先设置环境变量，避免硬编码路径问题
os.environ['INVENTORY_REPORT_DIR'] = os.path.join(_tmpdir, 'reports')
os.environ['INVENTORY_EXPORT_DIR'] = os.path.join(_tmpdir, 'exports')

from app import InventoryApp


class TestInventoryApp(unittest.TestCase):
    """InventoryApp 测试"""
    
    @classmethod
    def setUpClass(cls):
        # 初始化数据库
        from database import init_db
        init_db()
    
    def setUp(self):
        # 创建应用实例
        self.app = InventoryApp()
        # 修改硬编码路径为临时目录
        self.app.report_dir = os.path.join(_tmpdir, 'reports')
        self.app.export_dir = os.path.join(_tmpdir, 'exports')
        
        # 清空数据
        conn = sqlite3.connect(os.environ['INVENTORY_DB'])
        conn.execute("DELETE FROM products")
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM order_items")
        conn.commit()
        conn.close()
    
    def test_add_product_valid(self):
        """测试添加有效商品"""
        with patch('builtins.print') as mock_print:
            pid = self.app.add_product('测试商品', '29.99', '100', '电子产品')
            self.assertIsNotNone(pid)
            
            # 验证打印输出
            mock_print.assert_any_call('商品已添加: 测试商品 (ID: {})'.format(pid))
    
    def test_add_product_invalid_name(self):
        """测试添加无效商品名"""
        with patch('builtins.print') as mock_print:
            pid = self.app.add_product('测试', '29.99', '100')  # 禁用词
            self.assertIsNone(pid)
            mock_print.assert_called_with('ERROR: 无效商品名 "测试"')
    
    def test_add_product_invalid_price(self):
        """测试添加无效价格"""
        with patch('builtins.print') as mock_print:
            pid = self.app.add_product('测试商品', '-10', '100')
            self.assertIsNone(pid)
            mock_print.assert_called_with('ERROR: 无效价格 -10')
    
    def test_add_product_invalid_stock(self):
        """测试添加无效库存"""
        with patch('builtins.print') as mock_print:
            pid = self.app.add_product('测试商品', '29.99', '-10')
            self.assertIsNone(pid)
            mock_print.assert_called_with('ERROR: 无效库存 -10')
    
    def test_get_product_detail_exists(self):
        """测试获取存在的商品详情"""
        pid = self.app.add_product('测试商品', '29.99', '100')
        product = self.app.get_product_detail(pid)
        self.assertIsNotNone(product)
        self.assertEqual(product['name'], '测试商品')
    
    def test_get_product_detail_not_exists(self):
        """测试获取不存在的商品详情"""
        with patch('builtins.print') as mock_print:
            product = self.app.get_product_detail(999)
            self.assertIsNone(product)
            mock_print.assert_called_with('ERROR: 商品 999 不存在')
    
    def test_list_all_products(self):
        """测试列出所有商品"""
        self.app.add_product('商品A', '10.0', '5')
        self.app.add_product('商品B', '20.0', '10')
        
        with patch('builtins.print') as mock_print:
            products = self.app.list_all_products()
            self.assertEqual(len(products), 2)
            # 验证表格被打印
            self.assertTrue(mock_print.called)
    
    def test_list_all_products_empty(self):
        """测试列出空商品列表"""
        with patch('builtins.print') as mock_print:
            products = self.app.list_all_products()
            self.assertEqual(len(products), 0)
            mock_print.assert_called_with('暂无商品')
    
    def test_update_product_stock_valid(self):
        """测试有效库存更新"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        
        with patch('builtins.print') as mock_print:
            result = self.app.update_product_stock(pid, 50)
            self.assertTrue(result)
            
            # 验证商品库存已更新
            product = self.app.get_product_detail(pid)
            self.assertEqual(product['stock'], 150)
    
    def test_update_product_stock_insufficient(self):
        """测试库存不足的更新"""
        pid = self.app.add_product('测试商品', '10.0', '10')
        
        with patch('builtins.print') as mock_print:
            result = self.app.update_product_stock(pid, -20)  # 尝试减少20，但只有10
            self.assertFalse(result)
            mock_print.assert_called_with('ERROR: 库存不足 (当前: 10, 变更: -20)')
    
    def test_update_product_stock_low_stock_warning(self):
        """测试低库存预警"""
        pid = self.app.add_product('测试商品', '10.0', '15')
        
        with patch('builtins.print') as mock_print:
            result = self.app.update_product_stock(pid, -10)  # 减少到5，低于阈值10
            self.assertTrue(result)
            # 应该打印低库存警告
            mock_print.assert_any_call('⚠ 警告: 测试商品 库存偏低 (5)')
    
    def test_remove_product_exists(self):
        """测试删除存在的商品"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        
        with patch('builtins.print') as mock_print:
            result = self.app.remove_product(pid)
            self.assertTrue(result)
            mock_print.assert_called_with('商品已删除: 测试商品')
    
    def test_remove_product_not_exists(self):
        """测试删除不存在的商品"""
        with patch('builtins.print') as mock_print:
            result = self.app.remove_product(999)
            self.assertFalse(result)
            mock_print.assert_called_with('ERROR: 商品 999 不存在')
    
    def test_search_products(self):
        """测试搜索商品"""
        self.app.add_product('苹果手机', '5999.0', '50')
        self.app.add_product('华为手机', '3999.0', '100')
        self.app.add_product('苹果电脑', '12999.0', '30')
        
        with patch('builtins.print') as mock_print:
            results = self.app.search('苹果')
            self.assertEqual(len(results), 2)
            # 验证表格被打印
            self.assertTrue(mock_print.called)
    
    def test_search_products_no_results(self):
        """测试搜索无结果"""
        with patch('builtins.print') as mock_print:
            results = self.app.search('不存在的商品')
            self.assertEqual(len(results), 0)
            mock_print.assert_called_with('未找到包含 "不存在的商品" 的商品')
    
    def test_create_order_valid(self):
        """测试创建有效订单"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        
        with patch('builtins.print') as mock_print:
            order_id = self.app.create_order([(pid, 2)])
            self.assertIsNotNone(order_id)
            mock_print.assert_any_call('订单已创建: #{} 总金额: ¥20.00'.format(order_id))
            
            # 验证库存已扣减
            product = self.app.get_product_detail(pid)
            self.assertEqual(product['stock'], 98)
    
    def test_create_order_empty(self):
        """测试创建空订单"""
        with patch('builtins.print') as mock_print:
            order_id = self.app.create_order([])
            self.assertIsNone(order_id)
            mock_print.assert_called_with('ERROR: 订单不能为空')
    
    def test_create_order_exceeds_max_items(self):
        """测试超过最大商品数的订单"""
        items = [(1, 1)] * 51  # 创建51个商品项，超过默认的50
        
        with patch('builtins.print') as mock_print:
            order_id = self.app.create_order(items)
            self.assertIsNone(order_id)
            mock_print.assert_called_with('ERROR: 订单商品数超过上限 (50)')
    
    def test_create_order_product_not_exists(self):
        """测试创建包含不存在商品的订单"""
        with patch('builtins.print') as mock_print:
            order_id = self.app.create_order([(999, 1)])
            self.assertIsNone(order_id)
            mock_print.assert_called_with('ERROR: 商品 999 不存在')
    
    def test_create_order_insufficient_stock(self):
        """测试创建库存不足的订单"""
        pid = self.app.add_product('测试商品', '10.0', '5')
        
        with patch('builtins.print') as mock_print:
            order_id = self.app.create_order([(pid, 10)])  # 需要10，但只有5
            self.assertIsNone(order_id)
            mock_print.assert_called_with('ERROR: 测试商品 库存不足 (需要: 10, 实际: 5)')
    
    def test_get_order_detail_exists(self):
        """测试获取存在的订单详情"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        order_id = self.app.create_order([(pid, 2)])
        
        with patch('builtins.print') as mock_print:
            order = self.app.get_order_detail(order_id)
            self.assertIsNotNone(order)
            self.assertEqual(order['id'], order_id)
            # 验证订单详情被打印
            self.assertTrue(mock_print.called)
    
    def test_get_order_detail_not_exists(self):
        """测试获取不存在的订单详情"""
        with patch('builtins.print') as mock_print:
            order = self.app.get_order_detail(999)
            self.assertIsNone(order)
            mock_print.assert_called_with('ERROR: 订单 999 不存在')
    
    def test_confirm_order_valid(self):
        """测试确认有效订单"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        order_id = self.app.create_order([(pid, 2)])
        
        result = self.app.confirm_order(order_id)
        self.assertTrue(result)
        
        # 验证订单状态已更新
        from database import get_order
        order = get_order(order_id)
        self.assertEqual(order['status'], 'confirmed')
    
    def test_confirm_order_already_confirmed(self):
        """测试确认已确认的订单"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        order_id = self.app.create_order([(pid, 2)])
        self.app.confirm_order(order_id)  # 先确认一次
        
        with patch('builtins.print') as mock_print:
            result = self.app.confirm_order(order_id)  # 再次确认
            self.assertFalse(result)
            mock_print.assert_called_with('ERROR: 订单状态不允许确认 (当前: confirmed)')
    
    def test_ship_order_valid(self):
        """测试发货有效订单"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        order_id = self.app.create_order([(pid, 2)])
        self.app.confirm_order(order_id)
        
        result = self.app.ship_order(order_id)
        self.assertTrue(result)
        
        from database import get_order
        order = get_order(order_id)
        self.assertEqual(order['status'], 'shipped')
    
    def test_ship_order_not_confirmed(self):
        """测试发货未确认的订单"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        order_id = self.app.create_order([(pid, 2)])
        
        with patch('builtins.print') as mock_print:
            result = self.app.ship_order(order_id)
            self.assertFalse(result)
            mock_print.assert_called_with('ERROR: 未确认的订单不能发货 (当前: pending)')
    
    def test_complete_order_valid(self):
        """测试完成已发货的订单"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        order_id = self.app.create_order([(pid, 2)])
        self.app.confirm_order(order_id)
        self.app.ship_order(order_id)
        
        result = self.app.complete_order(order_id)
        self.assertTrue(result)
        
        from database import get_order
        order = get_order(order_id)
        self.assertEqual(order['status'], 'completed')
    
    def test_complete_order_not_shipped(self):
        """测试完成未发货的订单"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        order_id = self.app.create_order([(pid, 2)])
        self.app.confirm_order(order_id)
        
        with patch('builtins.print') as mock_print:
            result = self.app.complete_order(order_id)
            self.assertFalse(result)
            mock_print.assert_called_with('ERROR: 未发货的订单不能完成')
    
    def test_cancel_order_valid(self):
        """测试取消待处理的订单"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        order_id = self.app.create_order([(pid, 2)])
        
        result = self.app.cancel_order(order_id)
        self.assertTrue(result)
        
        from database import get_order
        order = get_order(order_id)
        self.assertEqual(order['status'], 'cancelled')
        
        # 验证库存已恢复
        product = self.app.get_product_detail(pid)
        self.assertEqual(product['stock'], 100)  # 恢复2个库存
    
    def test_cancel_order_shipped(self):
        """测试取消已发货的订单"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        order_id = self.app.create_order([(pid, 2)])
        self.app.confirm_order(order_id)
        self.app.ship_order(order_id)
        
        with patch('builtins.print') as mock_print:
            result = self.app.cancel_order(order_id)
            self.assertFalse(result)
            mock_print.assert_called_with('ERROR: 已发货/已完成的订单不能取消')
    
    def test_list_all_orders(self):
        """测试列出所有订单"""
        pid = self.app.add_product('测试商品', '10.0', '100')
        self.app.create_order([(pid, 2)])
        self.app.create_order([(pid, 3)])
        
        with patch('builtins.print') as mock_print:
            orders = self.app.list_all_orders()
            self.assertEqual(len(orders), 2)
            # 验证表格被打印
            self.assertTrue(mock_print.called)
    
    def test_generate_inventory_report(self):
        """测试生成库存报表"""
        # 创建测试数据
        self.app.add_product('商品A', '10.0', '5')   # 低库存
        self.app.add_product('商品B', '20.0', '15')  # 正常库存
        pid = self.app.add_product('商品C', '30.0', '100')
        self.app.create_order([(pid, 2)])
        
        # 创建报告目录
        os.makedirs(self.app.report_dir, exist_ok=True)
        
        with patch('builtins.print') as mock_print:
            report = self.app.generate_inventory_report()
            self.assertIsNotNone(report)
            
            # 验证报告内容
            self.assertEqual(report['summary']['total_products'], 3)
            self.assertGreater(report['summary']['total_value'], 0)
            self.assertEqual(report['summary']['low_stock_count'], 1)
            
            # 验证报告被打印
            self.assertTrue(mock_print.called)
    
    def test_generate_monthly_report(self):
        """测试生成月度报表（半成品功能）"""
        with patch('builtins.print') as mock_print:
            report = self.app.generate_monthly_report(2024, 1)
            self.assertIsNone(report)
            mock_print.assert_called_with('TODO: 月度报表 2024-01 尚未实现')
    
    def test_export_products(self):
        """测试导出商品"""
        self.app.add_product('商品A', '10.0', '5')
        self.app.add_product('商品B', '20.0', '15')
        
        # 创建导出目录
        os.makedirs(self.app.export_dir, exist_ok=True)
        
        with patch('builtins.print') as mock_print:
            self.app.export_products()
            # 验证导出成功（通过utils中的print验证）
            self.assertTrue(mock_print.called)
    
    def test_export_products_empty(self):
        """测试导出空商品列表"""
        with patch('builtins.print') as mock_print:
            self.app.export_products()
            mock_print.assert_called_with('没有可导出的商品')
    
    @patch('builtins.input', side_effect=['测试商品', '29.99', '100', ''])
    def test_import_products(self, mock_input):
        """测试导入商品"""
        # 创建测试CSV文件
        import csv
        csv_path = os.path.join(_tmpdir, 'test_import.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', '名称', '价格', '库存', '分类'])
            writer.writerow(['1', '导入商品A', '10.0', '5', '分类A'])
            writer.writerow(['2', '导入商品B', '20.0', '10', '分类B'])
        
        with patch('builtins.print') as mock_print:
            count = self.app.import_products(csv_path)
            self.assertEqual(count, 2)
            mock_print.assert_any_call('导入完成: 2/2 条')


# 需要导入sqlite3用于测试
import sqlite3

if __name__ == '__main__':
    unittest.main()