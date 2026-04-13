"""
定时任务
========
注册和管理周期性任务。
持久化到磁盘，支持启停和状态查询。

对标OpenHarness services/cron.py。

设计取舍：
  不自己实现cron表达式解析（避免引入croniter依赖），
  而是提供**基于间隔秒数的调度** + cron表达式存储（供外部解析或人类阅读）。
  ``get_due_jobs()`` 根据 ``interval_seconds`` 和 ``last_run`` 计算是否到期。

典型用法::

    sched = CronScheduler(config_dir)
    sched.register('cleanup', '每30分钟', 'python cleanup.py', interval_seconds=1800)
    sched.register('backup', '每天凌晨2点', 'python backup.py', interval_seconds=86400)

    due_jobs = sched.get_due_jobs()
    for job in due_jobs:
        run_job(job)
        sched.mark_completed(job.id, success=True)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from uuid import uuid4


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class CronJob:
    """定时任务定义。

    Attributes:
        id:               任务唯一ID。
        name:             任务名称（人类可读）。
        schedule:         cron表达式或描述文字（如 ``*/5 * * * *``）。
        command:          要执行的命令。
        interval_seconds: 执行间隔（秒）。实际调度以此为准。
        enabled:          是否启用。
        last_run:         上次执行时间戳。
        last_status:      上次执行结果: ``'success'`` | ``'failed'`` | ``''``。
        created_at:       创建时间戳。
    """

    id: str
    name: str
    schedule: str
    command: str
    interval_seconds: int = 0
    enabled: bool = True
    last_run: float = 0.0
    last_status: str = ''
    created_at: float = 0.0

    def to_dict(self) -> dict:
        """导出为JSON可序列化字典。"""
        return {
            'id': self.id,
            'name': self.name,
            'schedule': self.schedule,
            'command': self.command,
            'interval_seconds': self.interval_seconds,
            'enabled': self.enabled,
            'last_run': self.last_run,
            'last_status': self.last_status,
            'created_at': self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CronJob:
        """从字典恢复。"""
        return cls(
            id=d['id'],
            name=d['name'],
            schedule=d.get('schedule', ''),
            command=d['command'],
            interval_seconds=d.get('interval_seconds', 0),
            enabled=d.get('enabled', True),
            last_run=d.get('last_run', 0.0),
            last_status=d.get('last_status', ''),
            created_at=d.get('created_at', 0.0),
        )

    @property
    def is_due(self) -> bool:
        """基于interval_seconds判断是否到期。"""
        if not self.enabled or self.interval_seconds <= 0:
            return False
        if self.last_run == 0.0:
            return True  # 从未执行过
        return (time.time() - self.last_run) >= self.interval_seconds


# ---------------------------------------------------------------------------
# 调度器
# ---------------------------------------------------------------------------

class CronScheduler:
    """Cron调度器。

    以JSON文件持久化任务配置。
    通过 ``get_due_jobs()`` 查询到期任务，由调用方决定如何执行。

    Usage::

        sched = CronScheduler(config_dir)
        sched.register('cleanup', '每30分钟', 'python cleanup.py',
                        interval_seconds=1800)
        due_jobs = sched.get_due_jobs()
        for job in due_jobs:
            run_job(job)
            sched.mark_completed(job.id, success=True)
    """

    def __init__(self, config_dir: Path):
        self._config_dir = Path(config_dir)
        self._jobs_file = self._config_dir / 'cron_jobs.json'
        self._jobs: dict[str, CronJob] = {}
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    # -- 注册/注销 -------------------------------------------------------------

    def register(
        self,
        name: str,
        schedule: str,
        command: str,
        interval_seconds: int = 0,
    ) -> str:
        """注册定时任务，返回job_id。

        Args:
            name:             任务名称。
            schedule:         cron表达式或描述文字。
            command:          要执行的命令。
            interval_seconds: 执行间隔（秒），0表示手动触发。

        Returns:
            job_id (UUID hex)。
        """
        job_id = uuid4().hex[:12]
        job = CronJob(
            id=job_id,
            name=name,
            schedule=schedule,
            command=command,
            interval_seconds=interval_seconds,
            created_at=time.time(),
        )
        self._jobs[job_id] = job
        self._save()
        return job_id

    def unregister(self, job_id: str) -> bool:
        """取消注册指定任务。

        Returns:
            True 成功, False 任务不存在。
        """
        if job_id not in self._jobs:
            return False
        del self._jobs[job_id]
        self._save()
        return True

    # -- 启停 -----------------------------------------------------------------

    def enable(self, job_id: str) -> bool:
        """启用任务。"""
        job = self._jobs.get(job_id)
        if job is None:
            return False
        job.enabled = True
        self._save()
        return True

    def disable(self, job_id: str) -> bool:
        """禁用任务。"""
        job = self._jobs.get(job_id)
        if job is None:
            return False
        job.enabled = False
        self._save()
        return True

    # -- 调度查询 --------------------------------------------------------------

    def get_due_jobs(self) -> list[CronJob]:
        """获取当前应该执行的任务（已启用且到期）。"""
        return [job for job in self._jobs.values() if job.is_due]

    def mark_completed(self, job_id: str, success: bool):
        """标记任务本轮执行完成。

        Args:
            job_id:  任务ID。
            success: 是否执行成功。
        """
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.last_run = time.time()
        job.last_status = 'success' if success else 'failed'
        self._save()

    # -- 列表 -----------------------------------------------------------------

    def list_jobs(self) -> list[CronJob]:
        """列出所有任务，按创建时间升序。"""
        jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j.created_at)
        return jobs

    def get(self, job_id: str) -> Optional[CronJob]:
        """获取单个任务。"""
        return self._jobs.get(job_id)

    # -- 持久化 ----------------------------------------------------------------

    def _load(self):
        """从磁盘加载任务配置。"""
        if not self._jobs_file.exists():
            return
        try:
            text = self._jobs_file.read_text(encoding='utf-8')
            data = json.loads(text)
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, list):
            return
        for d in data:
            try:
                job = CronJob.from_dict(d)
                self._jobs[job.id] = job
            except (KeyError, TypeError):
                continue

    def _save(self):
        """保存任务配置到磁盘。"""
        data = [job.to_dict() for job in self._jobs.values()]
        try:
            self._jobs_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        except OSError:
            pass
