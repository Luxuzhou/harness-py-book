"""
任务数据持久化层
提供任务数据的CRUD操作和JSON持久化
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading


class TaskStore:
    """任务存储类，管理任务的增删改查和JSON持久化"""
    
    def __init__(self, filepath: str = "tasks.json") -> None:
        """
        初始化任务存储，指定JSON文件路径
        
        Args:
            filepath: JSON数据文件路径，支持环境变量TASK_DB_PATH配置
        """
        # 支持通过环境变量配置数据文件路径
        env_path = os.getenv("TASK_DB_PATH")
        if env_path:
            self.filepath = Path(env_path)
        else:
            self.filepath = Path(filepath)
        
        self._lock = threading.Lock()  # 线程安全锁
        self._data: Dict[str, Any] = {"next_id": 1, "tasks": []}
        self._load_data()
    
    def _load_data(self) -> None:
        """从JSON文件加载数据，如果文件不存在则初始化空数据"""
        try:
            if self.filepath.exists():
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                # 验证数据结构
                if "next_id" not in self._data or "tasks" not in self._data:
                    raise ValueError("Invalid data structure in JSON file")
            else:
                # 文件不存在，初始化空数据
                self._data = {"next_id": 1, "tasks": []}
                self._save_data()
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Failed to load data from {self.filepath}: {e}")
            print("Initializing with empty data...")
            self._data = {"next_id": 1, "tasks": []}
            self._save_data()
        except Exception as e:
            print(f"Error loading data: {e}")
            raise
    
    def _save_data(self) -> None:
        """保存数据到JSON文件"""
        try:
            # 确保目录存在
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving data to {self.filepath}: {e}")
            raise
    
    def add_task(self, description: str) -> Dict[str, Any]:
        """
        添加新任务，返回创建的任务对象
        
        Args:
            description: 任务描述
            
        Returns:
            创建的任务对象
            
        Raises:
            ValueError: 如果描述为空或过长
        """
        if not description or not description.strip():
            raise ValueError("Task description cannot be empty")
        
        if len(description.strip()) > 1000:
            raise ValueError("Task description too long (max 1000 characters)")
        
        with self._lock:
            task_id = self._data["next_id"]
            now = datetime.now().isoformat()
            
            task = {
                "id": task_id,
                "description": description.strip(),
                "created_at": now,
                "is_completed": False,
                "completed_at": None
            }
            
            self._data["tasks"].append(task)
            self._data["next_id"] = task_id + 1
            self._save_data()
            
            return task.copy()  # 返回副本避免外部修改
    
    def list_tasks(self, show_completed: bool = True) -> List[Dict[str, Any]]:
        """
        列出所有任务，可选是否显示已完成任务
        
        Args:
            show_completed: 是否显示已完成任务
            
        Returns:
            任务列表
        """
        with self._lock:
            if show_completed:
                return [task.copy() for task in self._data["tasks"]]
            else:
                return [task.copy() for task in self._data["tasks"] 
                       if not task["is_completed"]]
    
    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取任务，不存在返回None
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务对象或None
        """
        with self._lock:
            for task in self._data["tasks"]:
                if task["id"] == task_id:
                    return task.copy()
            return None
    
    def complete_task(self, task_id: int) -> bool:
        """
        标记任务为完成，成功返回True，任务不存在返回False
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功标记完成
        """
        with self._lock:
            for task in self._data["tasks"]:
                if task["id"] == task_id:
                    if not task["is_completed"]:
                        task["is_completed"] = True
                        task["completed_at"] = datetime.now().isoformat()
                        self._save_data()
                    return True
            return False
    
    def delete_task(self, task_id: int) -> bool:
        """
        删除任务，成功返回True，任务不存在返回False
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功删除
        """
        with self._lock:
            initial_length = len(self._data["tasks"])
            self._data["tasks"] = [task for task in self._data["tasks"] 
                                  if task["id"] != task_id]
            
            if len(self._data["tasks"]) < initial_length:
                self._save_data()
                return True
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """
        获取统计信息：总任务数、已完成数、未完成数
        
        Returns:
            统计信息字典
        """
        with self._lock:
            total = len(self._data["tasks"])
            completed = sum(1 for task in self._data["tasks"] 
                           if task["is_completed"])
            
            return {
                "total": total,
                "completed": completed,
                "pending": total - completed
            }
    
    def clear_all(self) -> None:
        """清空所有任务（主要用于测试）"""
        with self._lock:
            self._data = {"next_id": 1, "tasks": []}
            self._save_data()
