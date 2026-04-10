"""
仅有的几个测试 — 覆盖率极低，只测了最基本的路径。
这是遗留系统的典型状态。
"""

import os
import sys
import tempfile
import unittest

# 设置临时数据库
_tmpdir = tempfile.mkdtemp()
os.environ['INVENTORY_DB'] = os.path.join(_tmpdir, 'test.db')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from database import init_db, add_product, get_product, list_products
from utils import format_price, validate_price


class TestBasic(unittest.TestCase):
    """基础测试 — 只覆盖了商品添加和查询。"""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_add_and_get_product(self):
        pid = add_product('测试商品A', 29.99, 100, '电子产品')
        p = get_product(pid)
        self.assertIsNotNone(p)
        self.assertEqual(p['name'], '测试商品A')

    def test_list_products(self):
        products = list_products()
        self.assertIsInstance(products, list)

    def test_format_price(self):
        self.assertEqual(format_price(9.9), '¥9.90')
        self.assertEqual(format_price(15000), '¥1.5万')


class TestValidation(unittest.TestCase):

    def test_validate_price(self):
        self.assertTrue(validate_price(10))
        self.assertFalse(validate_price(-1))
        self.assertFalse(validate_price('abc'))


if __name__ == '__main__':
    unittest.main()
