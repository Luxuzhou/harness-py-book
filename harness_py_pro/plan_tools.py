"""
规划工具
========
对齐 DeepSeek-TUI 的 update_plan, checklist_*, task_* 工具体系。

工具直接操作 PlanStateManager（内存状态），状态由引擎每轮持久化并注入系统提示。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .config import AgentConfig
from .plan_state import PlanStateManager, StepStatus
from .tools import BaseTool


# ------------------------------------------------------------------
# update_plan
# ------------------------------------------------------------------

class UpdatePlanTool(BaseTool):
    """更新高层计划。"""

    name = 'update_plan'
    read_only = False
    planning_available = True

    def __init__(self, manager: PlanStateManager | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'update_plan',
            'description': (
                'Update the high-level strategic plan. '
                'Replaces the current plan with the provided steps. '
                'Each step has a status: pending, in_progress, or completed. '
                'Use this at the start of complex work to set direction, '
                'and update it as progress is made.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'steps': {
                        'type': 'array',
                        'description': 'List of plan steps. Each step is an object with {step: str, status: str}.',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'step': {'type': 'string', 'description': 'The step description'},
                                'status': {
                                    'type': 'string',
                                    'enum': ['pending', 'in_progress', 'completed'],
                                    'description': 'Step status',
                                },
                            },
                            'required': ['step', 'status'],
                        },
                    },
                    'explanation': {
                        'type': 'string',
                        'description': 'Optional explanation of the plan or current thinking.',
                    },
                },
                'required': ['steps'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'Plan manager not available'
        steps = args.get('steps', [])
        explanation = args.get('explanation', '')
        self.manager.plan.update(steps, explanation)
        self.manager.save()
        return True, f'Plan updated with {len(steps)} steps.\n{self.manager.plan.format_for_prompt()}'


# ------------------------------------------------------------------
# checklist_write
# ------------------------------------------------------------------

class ChecklistWriteTool(BaseTool):
    """写入检查清单（全量替换）。"""

    name = 'checklist_write'
    read_only = False
    planning_available = True

    def __init__(self, manager: PlanStateManager | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'checklist_write',
            'description': (
                'Write a checklist of concrete, verifiable steps for the current task. '
                'Replaces any existing checklist. '
                'Mark the first item as "in_progress". '
                'Update items using checklist_update as you complete them. '
                'This makes your work visible and keeps you focused.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'items': {
                        'type': 'array',
                        'description': 'List of checklist items. Each item is {content: str, status: str}.',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'content': {'type': 'string', 'description': 'The checklist item text'},
                                'status': {
                                    'type': 'string',
                                    'enum': ['pending', 'in_progress', 'completed'],
                                    'description': 'Item status',
                                },
                            },
                            'required': ['content', 'status'],
                        },
                    },
                },
                'required': ['items'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'Plan manager not available'
        items = args.get('items', [])
        self.manager.checklist = self.manager.checklist.__class__()  # reset
        for item in items:
            self.manager.checklist.add(item['content'], item.get('status', 'pending'))
        self.manager.save()
        return True, f'Checklist written with {len(items)} items.\n{self.manager.checklist.format_for_prompt()}'


# ------------------------------------------------------------------
# checklist_update
# ------------------------------------------------------------------

class ChecklistUpdateTool(BaseTool):
    """更新检查清单项状态。"""

    name = 'checklist_update'
    read_only = False
    planning_available = True

    def __init__(self, manager: PlanStateManager | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'checklist_update',
            'description': (
                'Update the status of one or more checklist items by their ID. '
                'Use this after completing a step or starting a new one.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'updates': {
                        'type': 'array',
                        'description': 'List of updates. Each is {id: int, status: str}.',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer', 'description': 'Item ID'},
                                'status': {
                                    'type': 'string',
                                    'enum': ['pending', 'in_progress', 'completed'],
                                    'description': 'New status',
                                },
                            },
                            'required': ['id', 'status'],
                        },
                    },
                },
                'required': ['updates'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'Plan manager not available'
        updates = args.get('updates', [])
        changed = 0
        for u in updates:
            if self.manager.checklist.update(u['id'], u['status']):
                changed += 1
        self.manager.save()
        return True, f'Updated {changed} item(s).\n{self.manager.checklist.format_for_prompt()}'


# ------------------------------------------------------------------
# checklist_list
# ------------------------------------------------------------------

class ChecklistListTool(BaseTool):
    """列出当前检查清单。"""

    name = 'checklist_list'
    read_only = True
    planning_available = True

    def __init__(self, manager: PlanStateManager | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'checklist_list',
            'description': 'List the current checklist with item IDs, content, and status.',
            'parameters': {
                'type': 'object',
                'properties': {},
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'Plan manager not available'
        return True, self.manager.checklist.format_for_prompt()


# ------------------------------------------------------------------
# task_create
# ------------------------------------------------------------------

class TaskCreateTool(BaseTool):
    """创建持久化任务。"""

    name = 'task_create'
    read_only = False
    planning_available = True

    def __init__(self, manager: PlanStateManager | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'task_create',
            'description': (
                'Create a durable work task. Tasks persist across turns and can be tracked. '
                'Use this for significant sub-tasks or work items that span multiple steps.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'title': {
                        'type': 'string',
                        'description': 'Short task title',
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Detailed task description',
                    },
                },
                'required': ['title'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'Plan manager not available'
        task = self.manager.tasks.create(
            title=args.get('title', ''),
            description=args.get('description', ''),
        )
        self.manager.save()
        return True, f'Task created: [{task.id}] {task.title}'


# ------------------------------------------------------------------
# task_list
# ------------------------------------------------------------------

class TaskListTool(BaseTool):
    """列出所有任务。"""

    name = 'task_list'
    read_only = True
    planning_available = True

    def __init__(self, manager: PlanStateManager | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'task_list',
            'description': 'List all tasks with their ID, title, status, and description.',
            'parameters': {
                'type': 'object',
                'properties': {},
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'Plan manager not available'
        tasks = self.manager.tasks.list()
        if not tasks:
            return True, 'No tasks.'
        lines = ['Tasks:']
        for t in tasks:
            symbol = {'pending': '○', 'in_progress': '◎', 'completed': '●'}.get(t['status'], '○')
            lines.append(f'  {symbol} [{t["id"]}] {t["title"]} ({t["status"]})')
        return True, '\n'.join(lines)


# ------------------------------------------------------------------
# task_update
# ------------------------------------------------------------------

class TaskUpdateTool(BaseTool):
    """更新任务状态。"""

    name = 'task_update'
    read_only = False
    planning_available = True

    def __init__(self, manager: PlanStateManager | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'task_update',
            'description': 'Update the status of a task by its ID.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'task_id': {'type': 'string', 'description': 'Task ID'},
                    'status': {
                        'type': 'string',
                        'enum': ['pending', 'in_progress', 'completed'],
                        'description': 'New status',
                    },
                },
                'required': ['task_id', 'status'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'Plan manager not available'
        ok = self.manager.tasks.update(args.get('task_id', ''), args.get('status', ''))
        self.manager.save()
        if ok:
            return True, 'Task updated.'
        return False, 'Task not found.'


# ------------------------------------------------------------------
# task_cancel
# ------------------------------------------------------------------

class TaskCancelTool(BaseTool):
    """取消/删除任务。"""

    name = 'task_cancel'
    read_only = False
    planning_available = True

    def __init__(self, manager: PlanStateManager | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'task_cancel',
            'description': 'Cancel (delete) a task by its ID.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'task_id': {'type': 'string', 'description': 'Task ID'},
                },
                'required': ['task_id'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'Plan manager not available'
        ok = self.manager.tasks.cancel(args.get('task_id', ''))
        self.manager.save()
        if ok:
            return True, 'Task cancelled.'
        return False, 'Task not found.'
