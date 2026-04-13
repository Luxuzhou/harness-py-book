"""
后台任务管理器
==============
spawn shell命令和子进程在后台运行，跟踪状态，捕获输出。
对标OpenHarness tasks/manager.py和Claude Code的Background Tasks。

设计要点：
  - 每个任务对应一个subprocess.Popen，stdout/stderr重定向到文件
  - 监控线程等待进程结束，自动更新状态
  - 线程安全：所有_tasks/_processes访问通过_lock保护
  - 输出文件存放在work_dir/.harness_tasks/{task_id}.out

典型用法：
    mgr = BackgroundTaskManager(Path('/tmp/project'))
    tid = mgr.create('python -m pytest tests/ -v')
    mgr.start(tid)
    # ... 做别的事 ...
    task = mgr.get(tid)
    if task and task.status == TaskStatus.COMPLETED:
        print(mgr.read_output(tid))
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

class TaskStatus(Enum):
    """后台任务生命周期状态。"""

    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    KILLED = 'killed'


@dataclass
class BackgroundTask:
    """单个后台任务的快照。

    Attributes:
        id:          唯一标识（UUID hex）。
        command:     shell命令字符串。
        label:       用户可读的任务描述（可选）。
        status:      当前生命周期状态。
        created_at:  创建时间戳。
        started_at:  启动时间戳（0.0 = 尚未启动）。
        ended_at:    结束时间戳（0.0 = 尚未结束）。
        exit_code:   进程退出码（None = 尚未退出）。
        output_file: stdout+stderr合并输出文件路径。
        error:       框架级错误信息（启动失败等）。
    """

    id: str
    command: str
    label: str = ''
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = 0.0
    started_at: float = 0.0
    ended_at: float = 0.0
    exit_code: Optional[int] = None
    output_file: Optional[Path] = None
    error: str = ''

    # -- 序列化 ---------------------------------------------------------------

    def to_dict(self) -> dict:
        """导出为可JSON序列化的字典。"""
        return {
            'id': self.id,
            'command': self.command,
            'label': self.label,
            'status': self.status.value,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'ended_at': self.ended_at,
            'exit_code': self.exit_code,
            'output_file': str(self.output_file) if self.output_file else None,
            'error': self.error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BackgroundTask:
        """从字典恢复。"""
        return cls(
            id=d['id'],
            command=d['command'],
            label=d.get('label', ''),
            status=TaskStatus(d['status']),
            created_at=d.get('created_at', 0.0),
            started_at=d.get('started_at', 0.0),
            ended_at=d.get('ended_at', 0.0),
            exit_code=d.get('exit_code'),
            output_file=Path(d['output_file']) if d.get('output_file') else None,
            error=d.get('error', ''),
        )

    # -- 便捷属性 -------------------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        """是否处于终态（completed/failed/killed）。"""
        return self.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.KILLED,
        )

    @property
    def elapsed(self) -> float:
        """已运行时长（秒）。运行中返回实时值，已结束返回总时长。"""
        if self.started_at == 0.0:
            return 0.0
        end = self.ended_at if self.ended_at > 0.0 else time.time()
        return end - self.started_at


# ---------------------------------------------------------------------------
# 管理器
# ---------------------------------------------------------------------------

class BackgroundTaskManager:
    """后台任务管理器。

    管理shell命令的生命周期：创建 → 启动 → 运行 → 完成/失败/杀死。
    每个任务的stdout和stderr合并重定向到一个文件，可随时读取。

    Usage::

        mgr = BackgroundTaskManager(work_dir)
        task_id = mgr.create('python -m pytest tests/ -v', label='run tests')
        mgr.start(task_id)
        status = mgr.get(task_id)
        output = mgr.read_output(task_id)
        mgr.stop(task_id)
        mgr.list_tasks()
    """

    def __init__(self, work_dir: Path):
        self.work_dir = Path(work_dir)
        self._tasks_dir = self.work_dir / '.harness_tasks'
        self._tasks: dict[str, BackgroundTask] = {}
        self._processes: dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()
        self._tasks_dir.mkdir(parents=True, exist_ok=True)

    # -- 创建 -----------------------------------------------------------------

    def create(self, command: str, label: str = '') -> str:
        """创建后台任务（不立即执行），返回task_id。

        Args:
            command: shell命令字符串，将通过 ``shell=True`` 执行。
            label:   用户可读的描述，方便列表展示。

        Returns:
            task_id (UUID hex字符串)。
        """
        task_id = uuid4().hex[:12]
        output_file = self._tasks_dir / f'{task_id}.out'

        task = BackgroundTask(
            id=task_id,
            command=command,
            label=label,
            created_at=time.time(),
            output_file=output_file,
        )

        with self._lock:
            self._tasks[task_id] = task

        self._persist_meta(task)
        return task_id

    # -- 启动 -----------------------------------------------------------------

    def start(self, task_id: str) -> bool:
        """启动指定任务。

        启动后，一个守护线程会等待进程结束并更新状态。

        Returns:
            True 启动成功, False 任务不存在或已在运行。
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status != TaskStatus.PENDING:
                return False

        # 打开输出文件（stdout + stderr 合并）
        out_fh = open(task.output_file, 'w', encoding='utf-8', errors='replace')

        try:
            proc = subprocess.Popen(
                task.command,
                shell=True,
                stdout=out_fh,
                stderr=subprocess.STDOUT,
                cwd=str(self.work_dir),
            )
        except OSError as exc:
            out_fh.close()
            with self._lock:
                task.status = TaskStatus.FAILED
                task.error = str(exc)
                task.ended_at = time.time()
            self._persist_meta(task)
            return False

        with self._lock:
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            self._processes[task_id] = proc

        self._persist_meta(task)

        # 启动守护线程，等待进程退出
        monitor = threading.Thread(
            target=self._monitor,
            args=(task_id, proc, out_fh),
            daemon=True,
        )
        monitor.start()

        return True

    # -- 停止 -----------------------------------------------------------------

    def stop(self, task_id: str) -> bool:
        """停止（杀死）正在运行的任务。

        Returns:
            True 已发送终止信号, False 任务不存在或不在运行。
        """
        with self._lock:
            task = self._tasks.get(task_id)
            proc = self._processes.get(task_id)
            if task is None or proc is None or task.status != TaskStatus.RUNNING:
                return False

        # terminate() 发送 SIGTERM (Unix) / TerminateProcess (Windows)
        try:
            proc.terminate()
        except OSError:
            pass

        # 给进程最多3秒优雅退出，否则 kill
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass

        # _monitor线程会最终更新状态为KILLED，但这里提前设置以保证即时可见
        with self._lock:
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.KILLED
                task.exit_code = proc.returncode
                task.ended_at = time.time()

        self._persist_meta(task)
        return True

    # -- 查询 -----------------------------------------------------------------

    def get(self, task_id: str) -> Optional[BackgroundTask]:
        """获取任务快照。返回None表示任务不存在。"""
        with self._lock:
            return self._tasks.get(task_id)

    def read_output(self, task_id: str, tail: int = 50) -> str:
        """读取任务输出（最后 *tail* 行）。

        Args:
            task_id: 任务ID。
            tail:    返回最后N行。0表示全部。

        Returns:
            输出文本。任务不存在或输出文件不存在时返回空字符串。
        """
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None or task.output_file is None:
            return ''
        try:
            text = task.output_file.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return ''
        if tail <= 0:
            return text
        lines = text.splitlines(keepends=True)
        return ''.join(lines[-tail:])

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[BackgroundTask]:
        """列出任务。可选按状态过滤。"""
        with self._lock:
            tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        # 按创建时间降序
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    # -- 清理 -----------------------------------------------------------------

    def cleanup_completed(self, max_age_seconds: float = 3600.0):
        """清理已完成的旧任务（及其输出文件）。

        只清理处于终态且年龄超过 *max_age_seconds* 的任务。
        """
        now = time.time()
        to_remove: list[str] = []

        with self._lock:
            for tid, task in self._tasks.items():
                if not task.is_terminal:
                    continue
                age = now - (task.ended_at if task.ended_at > 0 else task.created_at)
                if age >= max_age_seconds:
                    to_remove.append(tid)

        for tid in to_remove:
            with self._lock:
                task = self._tasks.pop(tid, None)
                self._processes.pop(tid, None)
            if task is None:
                continue
            # 删除输出文件
            if task.output_file and task.output_file.exists():
                try:
                    task.output_file.unlink()
                except OSError:
                    pass
            # 删除元数据文件
            meta_file = self._tasks_dir / f'{tid}.meta.json'
            if meta_file.exists():
                try:
                    meta_file.unlink()
                except OSError:
                    pass

    # -- 内部方法 --------------------------------------------------------------

    def _monitor(
        self,
        task_id: str,
        proc: subprocess.Popen,
        out_fh,
    ):
        """守护线程：等待进程结束，更新任务状态。"""
        try:
            proc.wait()
        except Exception:
            pass
        finally:
            try:
                out_fh.close()
            except Exception:
                pass

        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            # stop()可能已经设置了KILLED，不覆盖
            if task.status == TaskStatus.RUNNING:
                task.exit_code = proc.returncode
                task.ended_at = time.time()
                task.status = (
                    TaskStatus.COMPLETED
                    if proc.returncode == 0
                    else TaskStatus.FAILED
                )
            self._processes.pop(task_id, None)

        self._persist_meta(task)

    def _persist_meta(self, task: BackgroundTask):
        """将任务元数据写入磁盘（JSON格式），便于调试和恢复。"""
        meta_file = self._tasks_dir / f'{task.id}.meta.json'
        try:
            meta_file.write_text(
                json.dumps(task.to_dict(), ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        except OSError:
            pass
