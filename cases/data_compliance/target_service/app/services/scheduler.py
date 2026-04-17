"""
任务调度服务。

基于简易 interval / cron-like 表达式的调度器。生产场景可以替换为
APScheduler / Celery-beat，但对上层 Service 暴露的接口保持不变：
submit / cancel / list / tick。

本案例调度器是单进程、内存态的，适合演示定时扫描、批量报表等任务。
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


TaskFunc = Callable[[], Any]


@dataclass
class ScheduledTask:
    """一个可被调度的任务描述。"""
    task_id: str
    name: str
    fn: TaskFunc
    interval_seconds: Optional[int] = None  # 周期
    cron_expr: Optional[str] = None  # 简单 HH:MM 日频 cron
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None  # success / failed / running
    last_error: Optional[str] = None
    run_count: int = 0
    fail_count: int = 0
    max_runtime_seconds: int = 600
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)


class Scheduler:
    """
    任务调度器。

    用法：
        scheduler = Scheduler()
        scheduler.submit_interval('anomaly_scan', fn=my_scan, seconds=300)
        scheduler.start()   # 后台线程
        ...
        scheduler.stop()
    """

    def __init__(self, tick_seconds: float = 1.0):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._tick_seconds = tick_seconds
        self._run_history: List[Dict[str, Any]] = []
        self._max_history = 500

    # --- 任务提交 ---

    def submit_interval(
        self,
        name: str,
        fn: TaskFunc,
        seconds: int,
        start_after_seconds: int = 0,
    ) -> str:
        """
        提交周期任务。返回 task_id。

        seconds：多久执行一次
        start_after_seconds：相对现在的首次执行延迟
        """
        task = ScheduledTask(
            task_id=f'task-{uuid.uuid4().hex[:8]}',
            name=name,
            fn=fn,
            interval_seconds=seconds,
            next_run=datetime.now() + timedelta(seconds=start_after_seconds),
        )
        with self._lock:
            self._tasks[task.task_id] = task
        logger.info('submitted interval task %s (%s) every %ss',
                     task.task_id, name, seconds)
        return task.task_id

    def submit_daily(
        self,
        name: str,
        fn: TaskFunc,
        at_time: str,  # 'HH:MM'
    ) -> str:
        """提交每日固定时刻的任务（简化 cron）。"""
        next_run = self._next_daily_run(at_time)
        task = ScheduledTask(
            task_id=f'task-{uuid.uuid4().hex[:8]}',
            name=name,
            fn=fn,
            cron_expr=f'daily@{at_time}',
            next_run=next_run,
        )
        with self._lock:
            self._tasks[task.task_id] = task
        logger.info('submitted daily task %s (%s) at %s, next=%s',
                     task.task_id, name, at_time, next_run.isoformat())
        return task.task_id

    def submit_once(
        self,
        name: str,
        fn: TaskFunc,
        run_at: datetime,
    ) -> str:
        task = ScheduledTask(
            task_id=f'task-{uuid.uuid4().hex[:8]}',
            name=name,
            fn=fn,
            next_run=run_at,
        )
        with self._lock:
            self._tasks[task.task_id] = task
        logger.info('submitted once task %s (%s) at %s',
                     task.task_id, name, run_at.isoformat())
        return task.task_id

    # --- 任务管理 ---

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            return self._tasks.pop(task_id, None) is not None

    def pause(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].enabled = False
                return True
            return False

    def resume(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].enabled = True
                return True
            return False

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [self._serialize_task(t) for t in self._tasks.values()]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            t = self._tasks.get(task_id)
            return self._serialize_task(t) if t else None

    def recent_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self._run_history[-limit:])

    # --- 主循环 ---

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.warning('scheduler already running')
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info('scheduler started')

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info('scheduler stopped')

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            due = self._pick_due_tasks()
            for task in due:
                self._execute(task)
            self._stop_event.wait(self._tick_seconds)

    def _pick_due_tasks(self) -> List[ScheduledTask]:
        now = datetime.now()
        due = []
        with self._lock:
            for t in self._tasks.values():
                if not t.enabled or t.last_status == 'running':
                    continue
                if t.next_run and t.next_run <= now:
                    due.append(t)
        return due

    def _execute(self, task: ScheduledTask) -> None:
        start = datetime.now()
        with self._lock:
            task.last_status = 'running'
        try:
            result = task.fn()
            with self._lock:
                task.last_status = 'success'
                task.last_error = None
                task.run_count += 1
        except Exception as e:
            logger.warning('task %s failed: %s', task.task_id, e)
            with self._lock:
                task.last_status = 'failed'
                task.last_error = f'{type(e).__name__}: {e}'
                task.fail_count += 1
                task.run_count += 1
            result = None
        duration = (datetime.now() - start).total_seconds()
        with self._lock:
            task.last_run = start
            task.next_run = self._compute_next_run(task, start)
            self._record_run(task, start, duration, result)

    def _compute_next_run(
        self,
        task: ScheduledTask,
        last_start: datetime,
    ) -> Optional[datetime]:
        if task.interval_seconds:
            return last_start + timedelta(seconds=task.interval_seconds)
        if task.cron_expr and task.cron_expr.startswith('daily@'):
            hm = task.cron_expr.split('@', 1)[1]
            return self._next_daily_run(hm, reference=last_start + timedelta(seconds=1))
        return None  # one-shot

    @staticmethod
    def _next_daily_run(
        at_time: str,
        reference: Optional[datetime] = None,
    ) -> datetime:
        ref = reference or datetime.now()
        try:
            hh, mm = at_time.split(':')
            candidate = ref.replace(hour=int(hh), minute=int(mm),
                                     second=0, microsecond=0)
        except Exception:
            candidate = ref + timedelta(days=1)
        if candidate <= ref:
            candidate += timedelta(days=1)
        return candidate

    def _record_run(
        self,
        task: ScheduledTask,
        start: datetime,
        duration: float,
        result: Any,
    ) -> None:
        entry = {
            'task_id': task.task_id,
            'name': task.name,
            'started_at': start.isoformat(),
            'duration_seconds': round(duration, 3),
            'status': task.last_status,
            'error': task.last_error,
            'result_summary': str(result)[:200] if result else None,
        }
        self._run_history.append(entry)
        if len(self._run_history) > self._max_history:
            self._run_history = self._run_history[-self._max_history:]

    @staticmethod
    def _serialize_task(t: ScheduledTask) -> Dict[str, Any]:
        return {
            'task_id': t.task_id,
            'name': t.name,
            'interval_seconds': t.interval_seconds,
            'cron_expr': t.cron_expr,
            'next_run': t.next_run.isoformat() if t.next_run else None,
            'last_run': t.last_run.isoformat() if t.last_run else None,
            'last_status': t.last_status,
            'last_error': t.last_error,
            'run_count': t.run_count,
            'fail_count': t.fail_count,
            'enabled': t.enabled,
        }
