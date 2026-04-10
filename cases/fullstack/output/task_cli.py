"""
命令行任务管理工具
支持添加、列出、完成、删除任务，数据持久化到本地JSON文件
"""

import argparse
import sys
from typing import List, Optional
from task_store import TaskStore


def format_task(task: dict) -> str:
    """格式化单个任务为可读字符串"""
    status = "✓" if task["is_completed"] else "○"
    task_id = task["id"]
    description = task["description"]
    
    if task["is_completed"]:
        completed_at = task.get("completed_at", "unknown")
        return f"{status} [{task_id}] {description} (completed at {completed_at})"
    else:
        created_at = task.get("created_at", "unknown")
        return f"{status} [{task_id}] {description} (created at {created_at})"


def print_tasks(tasks: List[dict], title: Optional[str] = None) -> None:
    """打印任务列表"""
    if title:
        print(f"\n{title}")
        print("=" * len(title))
    
    if not tasks:
        print("暂无任务")
        return
    
    for task in tasks:
        print(format_task(task))


def add_task(store: TaskStore, description: str) -> None:
    """添加新任务"""
    try:
        task = store.add_task(description)
        print(f"✓ 任务添加成功！ID: {task['id']}")
    except ValueError as e:
        print(f"✗ 添加失败: {e}")
        sys.exit(1)


def list_tasks(store: TaskStore, show_all: bool = False, show_pending: bool = False) -> None:
    """列出任务"""
    if show_pending:
        tasks = store.list_tasks(show_completed=False)
        title = "待完成任务"
    elif show_all:
        tasks = store.list_tasks(show_completed=True)
        title = "所有任务"
    else:
        # 默认显示所有任务
        tasks = store.list_tasks(show_completed=True)
        title = "任务列表"
    
    stats = store.get_stats()
    print_tasks(tasks, title)
    print(f"\n统计: 总计 {stats['total']} | 已完成 {stats['completed']} | 待完成 {stats['pending']}")


def complete_task(store: TaskStore, task_id: int) -> None:
    """标记任务为完成"""
    try:
        task_id_int = int(task_id)
        if task_id_int <= 0:
            print("✗ 任务ID必须是正整数")
            sys.exit(1)
            
        if store.complete_task(task_id_int):
            print(f"✓ 任务 {task_id_int} 标记为完成")
        else:
            print(f"✗ 任务 {task_id_int} 不存在")
            sys.exit(1)
    except ValueError:
        print("✗ 任务ID必须是数字")
        sys.exit(1)


def delete_task(store: TaskStore, task_id: int) -> None:
    """删除任务"""
    try:
        task_id_int = int(task_id)
        if task_id_int <= 0:
            print("✗ 任务ID必须是正整数")
            sys.exit(1)
            
        if store.delete_task(task_id_int):
            print(f"✓ 任务 {task_id_int} 已删除")
        else:
            print(f"✗ 任务 {task_id_int} 不存在")
            sys.exit(1)
    except ValueError:
        print("✗ 任务ID必须是数字")
        sys.exit(1)


def main() -> None:
    """主函数：解析命令行参数并执行相应操作"""
    parser = argparse.ArgumentParser(
        description="命令行任务管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s add "Buy milk"          添加新任务
  %(prog)s list                    列出所有任务
  %(prog)s list --pending          只列出未完成任务
  %(prog)s done 1                  标记任务1为完成
  %(prog)s delete 1                删除任务1
  
环境变量:
  TASK_DB_PATH                     指定任务数据文件路径
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # add 命令
    add_parser = subparsers.add_parser("add", help="添加新任务")
    add_parser.add_argument("description", help="任务描述")
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="列出任务")
    list_group = list_parser.add_mutually_exclusive_group()
    list_group.add_argument("--all", action="store_true", help="显示所有任务（包括已完成）")
    list_group.add_argument("--pending", action="store_true", help="只显示未完成任务")
    
    # done 命令
    done_parser = subparsers.add_parser("done", help="标记任务为完成")
    done_parser.add_argument("task_id", help="任务ID")
    
    # delete 命令
    delete_parser = subparsers.add_parser("delete", help="删除任务")
    delete_parser.add_argument("task_id", help="任务ID")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 初始化任务存储
    try:
        store = TaskStore()
    except Exception as e:
        print(f"✗ 初始化任务存储失败: {e}")
        sys.exit(1)
    
    # 执行命令
    if args.command == "add":
        add_task(store, args.description)
    elif args.command == "list":
        list_tasks(store, args.all, args.pending)
    elif args.command == "done":
        complete_task(store, args.task_id)
    elif args.command == "delete":
        delete_task(store, args.task_id)


if __name__ == "__main__":
    main()
