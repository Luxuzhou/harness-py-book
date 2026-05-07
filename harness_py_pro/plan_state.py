"""
规划状态机
==========
对齐 DeepSeek-TUI 的 Plan + Checklist + Task 三层规划体系。

Plan:        高层战略步骤（update_plan）
Checklist:   当前任务下的细粒度执行步骤（checklist_write/list/update）
Task:        持久化工作对象（task_create/list/read/update/cancel）

状态每轮注入系统提示，让模型"看得见"自己的计划进度。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class StepStatus(str, Enum):
    """步骤状态。对齐 TUI 的 StepStatus。"""

    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'

    @classmethod
    def from_str(cls, value: str) -> StepStatus:
        v = value.strip().lower()
        mapping = {
            'pending': cls.PENDING,
            'in_progress': cls.IN_PROGRESS,
            'inprogress': cls.IN_PROGRESS,
            'completed': cls.COMPLETED,
            'done': cls.COMPLETED,
        }
        return mapping.get(v, cls.PENDING)

    @property
    def symbol(self) -> str:
        return {
            StepStatus.PENDING: '○',
            StepStatus.IN_PROGRESS: '◎',
            StepStatus.COMPLETED: '●',
        }[self]


# ------------------------------------------------------------------
# Plan
# ------------------------------------------------------------------

@dataclass
class PlanStep:
    step: str
    status: StepStatus = field(default=StepStatus.PENDING)
    explanation: str = ''

    def to_dict(self) -> dict:
        return {
            'step': self.step,
            'status': self.status.value,
            'explanation': self.explanation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PlanStep:
        return cls(
            step=d.get('step', ''),
            status=StepStatus.from_str(d.get('status', 'pending')),
            explanation=d.get('explanation', ''),
        )


@dataclass
class PlanState:
    """高层计划状态。"""

    steps: list[PlanStep] = field(default_factory=list)
    current_explanation: str = ''

    # ------------------------------------------------------------------
    # 更新
    # ------------------------------------------------------------------
    def update(self, steps: list[dict], explanation: str = '') -> None:
        """全量替换计划步骤。"""
        self.steps = [PlanStep.from_dict(s) for s in steps]
        if explanation:
            self.current_explanation = explanation

    def mark_in_progress(self, step_text: str) -> bool:
        for s in self.steps:
            if s.step == step_text:
                s.status = StepStatus.IN_PROGRESS
                return True
        return False

    def mark_completed(self, step_text: str) -> bool:
        for s in self.steps:
            if s.step == step_text:
                s.status = StepStatus.COMPLETED
                return True
        return False

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------
    def to_snapshot(self) -> dict:
        return {
            'steps': [s.to_dict() for s in self.steps],
            'explanation': self.current_explanation,
        }

    @classmethod
    def from_snapshot(cls, data: dict) -> PlanState:
        return cls(
            steps=[PlanStep.from_dict(s) for s in data.get('steps', [])],
            current_explanation=data.get('explanation', ''),
        )

    # ------------------------------------------------------------------
    # 格式化注入提示
    # ------------------------------------------------------------------
    def format_for_prompt(self) -> str:
        if not self.steps:
            return '（暂无计划）'
        lines = []
        for s in self.steps:
            lines.append(f'{s.status.symbol} {s.step}')
        if self.current_explanation:
            lines.append(f'\n💡 {self.current_explanation}')
        return '\n'.join(lines)


# ------------------------------------------------------------------
# Checklist
# ------------------------------------------------------------------

@dataclass
class ChecklistItem:
    id: int
    content: str
    status: StepStatus = field(default=StepStatus.PENDING)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'content': self.content,
            'status': self.status.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ChecklistItem:
        return cls(
            id=d.get('id', 0),
            content=d.get('content', ''),
            status=StepStatus.from_str(d.get('status', 'pending')),
        )


@dataclass
class ChecklistState:
    """当前任务下的检查清单。"""

    items: list[ChecklistItem] = field(default_factory=list)
    _next_id: int = 1

    def add(self, content: str, status: str = 'pending') -> ChecklistItem:
        item = ChecklistItem(
            id=self._next_id,
            content=content,
            status=StepStatus.from_str(status),
        )
        self._next_id += 1
        self.items.append(item)
        return item

    def update(self, item_id: int, status: str) -> bool:
        for item in self.items:
            if item.id == item_id:
                item.status = StepStatus.from_str(status)
                return True
        return False

    def list(self) -> list[dict]:
        return [i.to_dict() for i in self.items]

    def completion_pct(self) -> int:
        if not self.items:
            return 0
        completed = sum(1 for i in self.items if i.status == StepStatus.COMPLETED)
        return int(completed / len(self.items) * 100)

    def in_progress_id(self) -> int | None:
        for item in self.items:
            if item.status == StepStatus.IN_PROGRESS:
                return item.id
        return None

    def to_snapshot(self) -> dict:
        return {
            'items': [i.to_dict() for i in self.items],
            'next_id': self._next_id,
        }

    @classmethod
    def from_snapshot(cls, data: dict) -> ChecklistState:
        state = cls(
            items=[ChecklistItem.from_dict(i) for i in data.get('items', [])],
            _next_id=data.get('next_id', 1),
        )
        return state

    def format_for_prompt(self) -> str:
        if not self.items:
            return '（暂无检查清单）'
        lines = []
        pct = self.completion_pct()
        lines.append(f'进度: {pct}% ({sum(1 for i in self.items if i.status == StepStatus.COMPLETED)}/{len(self.items)})')
        for item in self.items:
            lines.append(f'  {item.status.symbol} [{item.id}] {item.content}')
        return '\n'.join(lines)


# ------------------------------------------------------------------
# Task (持久化工作对象)
# ------------------------------------------------------------------

@dataclass
class TaskItem:
    id: str
    title: str
    description: str
    status: StepStatus = StepStatus.PENDING
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status.value,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TaskItem:
        return cls(
            id=d.get('id', ''),
            title=d.get('title', ''),
            description=d.get('description', ''),
            status=StepStatus.from_str(d.get('status', 'pending')),
            created_at=d.get('created_at', 0.0),
            updated_at=d.get('updated_at', 0.0),
        )


@dataclass
class TaskRegistry:
    """持久化任务注册表。"""

    tasks: dict[str, TaskItem] = field(default_factory=dict)

    def create(self, title: str, description: str = '') -> TaskItem:
        task_id = f'task_{int(time.time() * 1000)}'
        now = time.time()
        task = TaskItem(
            id=task_id,
            title=title,
            description=description,
            status=StepStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        self.tasks[task_id] = task
        return task

    def get(self, task_id: str) -> TaskItem | None:
        return self.tasks.get(task_id)

    def list(self) -> list[dict]:
        return [t.to_dict() for t in self.tasks.values()]

    def update(self, task_id: str, status: str) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False
        task.status = StepStatus.from_str(status)
        task.updated_at = time.time()
        return True

    def cancel(self, task_id: str) -> bool:
        if task_id in self.tasks:
            del self.tasks[task_id]
            return True
        return False

    def to_snapshot(self) -> dict:
        return {'tasks': [t.to_dict() for t in self.tasks.values()]}

    @classmethod
    def from_snapshot(cls, data: dict) -> TaskRegistry:
        return cls(
            tasks={t['id']: TaskItem.from_dict(t) for t in data.get('tasks', [])},
        )


# ------------------------------------------------------------------
# 状态管理器
# ------------------------------------------------------------------

class PlanStateManager:
    """
    管理 PlanState + ChecklistState + TaskRegistry 的持久化。
    每个 session 独立一份状态。
    """

    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.plan = PlanState()
        self.checklist = ChecklistState()
        self.tasks = TaskRegistry()
        self._load()

    def _load(self) -> None:
        plan_file = self.session_dir / 'plan_state.json'
        if plan_file.exists():
            try:
                data = json.loads(plan_file.read_text(encoding='utf-8'))
                self.plan = PlanState.from_snapshot(data)
            except (json.JSONDecodeError, KeyError):
                pass

        checklist_file = self.session_dir / 'checklist_state.json'
        if checklist_file.exists():
            try:
                data = json.loads(checklist_file.read_text(encoding='utf-8'))
                self.checklist = ChecklistState.from_snapshot(data)
            except (json.JSONDecodeError, KeyError):
                pass

        tasks_file = self.session_dir / 'tasks.json'
        if tasks_file.exists():
            try:
                data = json.loads(tasks_file.read_text(encoding='utf-8'))
                self.tasks = TaskRegistry.from_snapshot(data)
            except (json.JSONDecodeError, KeyError):
                pass

    def save(self) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)

        plan_file = self.session_dir / 'plan_state.json'
        plan_file.write_text(
            json.dumps(self.plan.to_snapshot(), ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        checklist_file = self.session_dir / 'checklist_state.json'
        checklist_file.write_text(
            json.dumps(self.checklist.to_snapshot(), ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        tasks_file = self.session_dir / 'tasks.json'
        tasks_file.write_text(
            json.dumps(self.tasks.to_snapshot(), ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    def format_for_prompt(self) -> str:
        """格式化为提示注入文本。"""
        parts = []
        plan_text = self.plan.format_for_prompt()
        if plan_text and plan_text != '（暂无计划）':
            parts.append(f'## Plan\n{plan_text}')

        checklist_text = self.checklist.format_for_prompt()
        if checklist_text and checklist_text != '（暂无检查清单）':
            parts.append(f'## Checklist\n{checklist_text}')

        if self.tasks.tasks:
            task_lines = ['## Tasks']
            for t in self.tasks.tasks.values():
                task_lines.append(f'  {t.status.symbol} [{t.id}] {t.title}')
            parts.append('\n'.join(task_lines))

        return '\n\n'.join(parts) if parts else ''
