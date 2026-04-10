# 技术方案

## 架构设计

### 模块划分和职责说明

1. **task_cli.py** (主程序，约80行)
   - 职责：命令行接口，解析用户输入，调用数据层接口
   - 功能：
     - 解析命令行参数（使用argparse）
     - 处理4个命令：add、list、done、delete
     - 格式化输出显示
     - 错误处理和用户友好提示

2. **task_store.py** (数据持久化层，约120行)
   - 职责：任务数据的CRUD操作和JSON持久化
   - 功能：
     - 初始化数据文件（如果不存在）
     - 加载/保存JSON数据
     - 任务ID自动递增管理
     - 提供任务增删改查接口
     - 线程安全的数据访问

3. **tests/test_task_cli.py** (测试文件，约100行)
   - 职责：单元测试，覆盖所有功能和边界条件
   - 使用pytest框架
   - 包含临时文件管理，避免污染实际数据

### 数据流向
```
用户输入 → task_cli.py → task_store.py → JSON文件
```

## 数据结构

### 任务对象格式
```json
{
  "id": 1,
  "description": "Buy milk",
  "created_at": "2024-01-15T10:30:00",
  "is_completed": false,
  "completed_at": null
}
```

### JSON文件格式（tasks.json）
```json
{
  "next_id": 5,
  "tasks": [
    {
      "id": 1,
      "description": "Buy milk",
      "created_at": "2024-01-15T10:30:00",
      "is_completed": false,
      "completed_at": null
    },
    {
      "id": 2,
      "description": "Read book",
      "created_at": "2024-01-15T11:00:00",
      "is_completed": true,
      "completed_at": "2024-01-16T09:00:00"
    }
  ]
}
```

## 文件清单

| 文件 | 职责 | 预估行数 |
|------|------|---------|
| `output/task_cli.py` | 命令行接口主程序 | 80 |
| `output/task_store.py` | 数据持久化层 | 120 |
| `output/tests/test_task_cli.py` | 单元测试 | 100 |
| `output/tasks.json` | 数据文件（运行时生成） | - |

## 接口定义

### task_store.py 公开接口

```python
class TaskStore:
    def __init__(self, filepath: str = "tasks.json") -> None:
        """初始化任务存储，指定JSON文件路径"""
        
    def add_task(self, description: str) -> Dict[str, Any]:
        """添加新任务，返回创建的任务对象"""
        
    def list_tasks(self, show_completed: bool = True) -> List[Dict[str, Any]]:
        """列出所有任务，可选是否显示已完成任务"""
        
    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取任务，不存在返回None"""
        
    def complete_task(self, task_id: int) -> bool:
        """标记任务为完成，成功返回True，任务不存在返回False"""
        
    def delete_task(self, task_id: int) -> bool:
        """删除任务，成功返回True，任务不存在返回False"""
        
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息：总任务数、已完成数、未完成数"""
```

### task_cli.py 命令行接口

```bash
# 添加任务
python task_cli.py add "任务描述"

# 列出所有任务
python task_cli.py list
python task_cli.py list --all  # 显示包括已完成的任务
python task_cli.py list --pending  # 只显示未完成的任务

# 标记任务完成
python task_cli.py done <task_id>

# 删除任务
python task_cli.py delete <task_id>

# 显示帮助
python task_cli.py --help
```

## 测试用例设计

| 用例ID | 描述 | 预期结果 |
|--------|------|---------|
| TC-001 | 添加新任务 | 任务成功添加到JSON文件，返回正确ID |
| TC-002 | 添加空描述任务 | 提示错误，任务不添加 |
| TC-003 | 列出所有任务（空列表） | 显示"暂无任务"提示 |
| TC-004 | 列出所有任务（有数据） | 正确格式化显示所有任务 |
| TC-005 | 列出未完成任务 | 只显示is_completed=False的任务 |
| TC-006 | 标记存在的任务为完成 | 任务is_completed=True，completed_at设置时间 |
| TC-007 | 标记不存在的任务为完成 | 提示"任务不存在"错误 |
| TC-008 | 删除存在的任务 | 任务从列表中移除 |
| TC-009 | 删除不存在的任务 | 提示"任务不存在"错误 |
| TC-010 | 数据文件不存在时初始化 | 自动创建空数据文件 |
| TC-011 | 数据文件损坏时处理 | 提示错误并创建新文件 |
| TC-012 | 并发访问测试 | 数据一致性保持 |
| TC-013 | ID自动递增 | 新任务ID正确递增 |
| TC-014 | 统计信息正确性 | get_stats()返回正确计数 |
| TC-015 | 命令行参数解析 | 正确解析各种参数组合 |

### 边界条件测试
1. 空描述的任务添加
2. 超长描述的任务添加（>1000字符）
3. 负数的任务ID操作
4. 非常大的任务ID操作
5. JSON文件权限问题
6. 磁盘空间不足情况
7. 特殊字符的任务描述
8. 同时添加大量任务

## 实现要点

1. **错误处理**：
   - 文件读写异常处理
   - JSON解析异常处理
   - 用户输入验证
   - 任务不存在处理

2. **用户体验**：
   - 清晰的命令行帮助
   - 友好的错误提示
   - 彩色输出（可选）
   - 进度提示

3. **代码质量**：
   - 完整的type hints
   - 详细的docstring
   - 模块化设计
   - 可测试的接口

4. **性能考虑**：
   - 小文件操作，性能不是瓶颈
   - 内存使用优化
   - 避免不必要的文件读写

## 依赖约束
- Python 3.10+
- 仅使用标准库：argparse, json, pathlib, datetime, typing
- 测试使用pytest（如果环境支持）或unittest