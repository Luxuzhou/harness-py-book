"""
任务管理工具的单元测试
"""

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

# 导入被测试模块
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from task_store import TaskStore
import task_cli


class TestTaskStore(unittest.TestCase):
    """TaskStore类的单元测试"""
    
    def setUp(self):
        """每个测试用例前执行：创建临时文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test_tasks.json"
        
    def tearDown(self):
        """每个测试用例后执行：清理临时文件"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_init_creates_file_if_not_exists(self):
        """测试：文件不存在时自动创建"""
        store = TaskStore(str(self.test_file))
        self.assertTrue(self.test_file.exists())
        
        with open(self.test_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data["next_id"], 1)
            self.assertEqual(data["tasks"], [])
    
    def test_init_loads_existing_file(self):
        """测试：加载已存在的文件"""
        # 创建测试数据
        test_data = {
            "next_id": 3,
            "tasks": [
                {
                    "id": 1,
                    "description": "Test task 1",
                    "created_at": "2024-01-01T00:00:00",
                    "is_completed": False,
                    "completed_at": None
                }
            ]
        }
        
        with open(self.test_file, 'w') as f:
            json.dump(test_data, f)
        
        store = TaskStore(str(self.test_file))
        tasks = store.list_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["description"], "Test task 1")
        self.assertEqual(store.get_stats()["total"], 1)
    
    def test_add_task(self):
        """测试：添加新任务"""
        store = TaskStore(str(self.test_file))
        
        task = store.add_task("Test task")
        self.assertEqual(task["description"], "Test task")
        self.assertEqual(task["id"], 1)
        self.assertFalse(task["is_completed"])
        
        # 验证数据已保存
        with open(self.test_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data["next_id"], 2)
            self.assertEqual(len(data["tasks"]), 1)
    
    def test_add_task_empty_description(self):
        """测试：添加空描述任务应失败"""
        store = TaskStore(str(self.test_file))
        
        with self.assertRaises(ValueError):
            store.add_task("")
        
        with self.assertRaises(ValueError):
            store.add_task("   ")
    
    def test_add_task_long_description(self):
        """测试：添加过长描述任务应失败"""
        store = TaskStore(str(self.test_file))
        
        long_desc = "x" * 1001
        with self.assertRaises(ValueError):
            store.add_task(long_desc)
    
    def test_list_tasks(self):
        """测试：列出任务"""
        store = TaskStore(str(self.test_file))
        
        # 添加一些任务
        store.add_task("Task 1")
        store.add_task("Task 2")
        store.complete_task(1)
        
        # 列出所有任务
        all_tasks = store.list_tasks(show_completed=True)
        self.assertEqual(len(all_tasks), 2)
        
        # 只列出未完成任务
        pending_tasks = store.list_tasks(show_completed=False)
        self.assertEqual(len(pending_tasks), 1)
        self.assertEqual(pending_tasks[0]["id"], 2)
    
    def test_get_task(self):
        """测试：获取单个任务"""
        store = TaskStore(str(self.test_file))
        
        store.add_task("Test task")
        
        task = store.get_task(1)
        self.assertIsNotNone(task)
        self.assertEqual(task["description"], "Test task")
        
        # 获取不存在的任务
        task = store.get_task(999)
        self.assertIsNone(task)
    
    def test_complete_task(self):
        """测试：标记任务为完成"""
        store = TaskStore(str(self.test_file))
        
        store.add_task("Test task")
        
        # 标记为完成
        result = store.complete_task(1)
        self.assertTrue(result)
        
        task = store.get_task(1)
        self.assertTrue(task["is_completed"])
        self.assertIsNotNone(task["completed_at"])
        
        # 标记不存在的任务
        result = store.complete_task(999)
        self.assertFalse(result)
    
    def test_delete_task(self):
        """测试：删除任务"""
        store = TaskStore(str(self.test_file))
        
        store.add_task("Task 1")
        store.add_task("Task 2")
        
        # 删除存在的任务
        result = store.delete_task(1)
        self.assertTrue(result)
        self.assertEqual(store.get_stats()["total"], 1)
        
        # 删除不存在的任务
        result = store.delete_task(999)
        self.assertFalse(result)
        self.assertEqual(store.get_stats()["total"], 1)
    
    def test_get_stats(self):
        """测试：获取统计信息"""
        store = TaskStore(str(self.test_file))
        
        # 初始状态
        stats = store.get_stats()
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["completed"], 0)
        self.assertEqual(stats["pending"], 0)
        
        # 添加任务后
        store.add_task("Task 1")
        store.add_task("Task 2")
        store.complete_task(1)
        
        stats = store.get_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["pending"], 1)
    
    def test_clear_all(self):
        """测试：清空所有任务"""
        store = TaskStore(str(self.test_file))
        
        store.add_task("Task 1")
        store.add_task("Task 2")
        store.clear_all()
        
        stats = store.get_stats()
        self.assertEqual(stats["total"], 0)
        
        # 验证文件也被清空
        with open(self.test_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data["next_id"], 1)
            self.assertEqual(data["tasks"], [])
    
    def test_thread_safety(self):
        """测试：线程安全（简化版）"""
        import threading
        
        store = TaskStore(str(self.test_file))
        
        def add_multiple_tasks(start, count):
            for i in range(count):
                store.add_task(f"Task {start + i}")
        
        # 创建多个线程同时添加任务
        threads = []
        for i in range(5):
            t = threading.Thread(target=add_multiple_tasks, args=(i*10, 10))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证所有任务都被添加且ID连续
        stats = store.get_stats()
        self.assertEqual(stats["total"], 50)
        
        # 验证ID从1到50连续
        tasks = store.list_tasks()
        task_ids = [task["id"] for task in tasks]
        self.assertEqual(sorted(task_ids), list(range(1, 51)))


class TestTaskCLI(unittest.TestCase):
    """命令行接口的单元测试"""
    
    def setUp(self):
        """每个测试用例前执行：创建临时文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test_tasks.json"
        
        # 设置环境变量
        os.environ["TASK_DB_PATH"] = str(self.test_file)
    
    def tearDown(self):
        """每个测试用例后执行：清理临时文件和环境变量"""
        import shutil
        shutil.rmtree(self.temp_dir)
        if "TASK_DB_PATH" in os.environ:
            del os.environ["TASK_DB_PATH"]
    
    def test_format_task(self):
        """测试：格式化任务"""
        task = {
            "id": 1,
            "description": "Test task",
            "created_at": "2024-01-01T00:00:00",
            "is_completed": False,
            "completed_at": None
        }
        
        formatted = task_cli.format_task(task)
        self.assertIn("[1] Test task", formatted)
        self.assertIn("created at", formatted)
        
        # 已完成任务
        task["is_completed"] = True
        task["completed_at"] = "2024-01-02T00:00:00"
        formatted = task_cli.format_task(task)
        self.assertIn("completed at", formatted)
    
    @patch('sys.argv', ['task_cli.py', 'add', 'Test task'])
    @patch('task_cli.TaskStore')
    def test_add_command(self, mock_store_class):
        """测试：add命令"""
        mock_store = MagicMock()
        mock_task = {"id": 1, "description": "Test task"}
        mock_store.add_task.return_value = mock_task
        mock_store_class.return_value = mock_store
        
        with patch('sys.stdout') as mock_stdout:
            task_cli.main()
        
        mock_store.add_task.assert_called_once_with("Test task")
    
    @patch('sys.argv', ['task_cli.py', 'list'])
    @patch('task_cli.TaskStore')
    def test_list_command(self, mock_store_class):
        """测试：list命令"""
        mock_store = MagicMock()
        mock_store.list_tasks.return_value = []
        mock_store.get_stats.return_value = {"total": 0, "completed": 0, "pending": 0}
        mock_store_class.return_value = mock_store
        
        with patch('sys.stdout') as mock_stdout:
            task_cli.main()
        
        mock_store.list_tasks.assert_called_once_with(show_completed=True)
    
    @patch('sys.argv', ['task_cli.py', 'done', '1'])
    @patch('task_cli.TaskStore')
    def test_done_command(self, mock_store_class):
        """测试：done命令"""
        mock_store = MagicMock()
        mock_store.complete_task.return_value = True
        mock_store_class.return_value = mock_store
        
        with patch('sys.stdout') as mock_stdout:
            task_cli.main()
        
        mock_store.complete_task.assert_called_once_with(1)
    
    @patch('sys.argv', ['task_cli.py', 'delete', '1'])
    @patch('task_cli.TaskStore')
    def test_delete_command(self, mock_store_class):
        """测试：delete命令"""
        mock_store = MagicMock()
        mock_store.delete_task.return_value = True
        mock_store_class.return_value = mock_store
        
        with patch('sys.stdout') as mock_stdout:
            task_cli.main()
        
        mock_store.delete_task.assert_called_once_with(1)
    
    def test_invalid_task_id(self):
        """测试：无效的任务ID"""
        store = TaskStore(str(self.test_file))
        
        # 测试负数ID
        with patch('sys.argv', ['task_cli.py', 'done', '-1']):
            with self.assertRaises(SystemExit) as cm:
                task_cli.main()
            self.assertEqual(cm.exception.code, 1)
        
        # 测试非数字ID
        with patch('sys.argv', ['task_cli.py', 'done', 'abc']):
            with self.assertRaises(SystemExit) as cm:
                task_cli.main()
            self.assertEqual(cm.exception.code, 1)


class TestIntegration(unittest.TestCase):
    """集成测试：模拟真实使用场景"""
    
    def setUp(self):
        """每个测试用例前执行：创建临时文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test_tasks.json"
        os.environ["TASK_DB_PATH"] = str(self.test_file)
    
    def tearDown(self):
        """每个测试用例后执行：清理"""
        import shutil
        shutil.rmtree(self.temp_dir)
        if "TASK_DB_PATH" in os.environ:
            del os.environ["TASK_DB_PATH"]
    
    def test_full_workflow(self):
        """测试：完整的工作流程"""
        # 1. 添加任务
        with patch('sys.argv', ['task_cli.py', 'add', 'Buy milk']):
            task_cli.main()
        
        with patch('sys.argv', ['task_cli.py', 'add', 'Read book']):
            task_cli.main()
        
        # 2. 列出任务
        with patch('sys.argv', ['task_cli.py', 'list']), \
             patch('sys.stdout') as mock_stdout:
            task_cli.main()
        
        # 3. 标记任务完成
        with patch('sys.argv', ['task_cli.py', 'done', '1']):
            task_cli.main()
        
        # 4. 删除任务
        with patch('sys.argv', ['task_cli.py', 'delete', '2']):
            task_cli.main()
        
        # 验证最终状态
        store = TaskStore(str(self.test_file))
        stats = store.get_stats()
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["pending"], 0)
        
        task = store.get_task(1)
        self.assertIsNotNone(task)
        self.assertTrue(task["is_completed"])
    
    def test_empty_database(self):
        """测试：空数据库的情况"""
        # 列出空数据库
        with patch('sys.argv', ['task_cli.py', 'list']), \
             patch('sys.stdout') as mock_stdout:
            task_cli.main()
        
        # 尝试操作不存在的任务
        with patch('sys.argv', ['task_cli.py', 'done', '1']):
            with self.assertRaises(SystemExit) as cm:
                task_cli.main()
            self.assertEqual(cm.exception.code, 1)
        
        with patch('sys.argv', ['task_cli.py', 'delete', '1']):
            with self.assertRaises(SystemExit) as cm:
                task_cli.main()
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()