"""
异步子代理管理器
================
对齐 DeepSeek-TUI 的异步子代理模型：

  - spawn()  → 立即返回 agent_id，子代理在后台线程运行
  - result() → 查询状态/结果
  - wait()   → 阻塞等待完成
  - cancel() → 取消子代理
  - list()   → 列出所有子代理

子代理完成后，引擎每轮 poll 并将其结果注入到父代理的 message history。
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class SubAgentStatus(str, Enum):
    """子代理状态。"""

    RUNNING = 'running'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    FAILED = 'failed'


@dataclass
class SubAgentRecord:
    """子代理运行记录。"""

    agent_id: str
    agent_type: str
    prompt: str
    status: SubAgentStatus = SubAgentStatus.RUNNING
    result_summary: str = ''
    result_turns: int = 0
    result_tokens: int = 0
    result_stop_reason: str = ''
    error: str = ''
    started_at: float = 0.0
    completed_at: float | None = None

    def to_dict(self) -> dict:
        return {
            'agent_id': self.agent_id,
            'agent_type': self.agent_type,
            'status': self.status.value,
            'result_summary': self.result_summary[:500],
            'result_turns': self.result_turns,
            'result_tokens': self.result_tokens,
            'result_stop_reason': self.result_stop_reason,
            'error': self.error,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'duration_sec': (
                (self.completed_at or time.time()) - self.started_at
                if self.started_at
                else 0
            ),
        }


class SubAgentManager:
    """
    子代理管理器。

    线程安全，支持并发 spawn、查询、取消。
    """

    def __init__(self, max_concurrent: int = 10, session_dir: Path | None = None):
        self._records: dict[str, SubAgentRecord] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent, thread_name_prefix='subagent-')
        self._session_dir = session_dir
        self._completion_callbacks: list[Callable[[SubAgentRecord], None]] = []
        self._running_count = 0
        self._polled_ids: set[str] = set()

    @property
    def running_count(self) -> int:
        with self._lock:
            return self._running_count

    def register_completion_callback(self, callback: Callable[[SubAgentRecord], None]):
        """注册子代理完成回调。"""
        self._completion_callbacks.append(callback)

    def spawn(
        self,
        agent_id: str,
        prompt: str,
        agent_type: str,
        runner: Callable[[], tuple[bool, str]],
    ) -> SubAgentRecord:
        """
        启动一个子代理。

        runner: 实际执行子代理的回调，签名 () -> (ok, summary_str)
        """
        record = SubAgentRecord(
            agent_id=agent_id,
            agent_type=agent_type,
            prompt=prompt,
            status=SubAgentStatus.RUNNING,
            started_at=time.time(),
        )

        with self._lock:
            self._records[agent_id] = record
            self._running_count += 1

        # 提交到线程池后台执行
        def _run_and_capture():
            try:
                ok, summary = runner()
                with self._lock:
                    record.status = SubAgentStatus.COMPLETED if ok else SubAgentStatus.FAILED
                    record.result_summary = summary
                    record.completed_at = time.time()
                    self._running_count -= 1
            except Exception as e:
                with self._lock:
                    record.status = SubAgentStatus.FAILED
                    record.error = str(e)
                    record.completed_at = time.time()
                    self._running_count -= 1

            # 触发回调
            for cb in self._completion_callbacks:
                try:
                    cb(record)
                except Exception:
                    pass

            # 持久化
            if self._session_dir:
                self._save_record(record)

        self._executor.submit(_run_and_capture)
        return record

    def get_result(self, agent_id: str) -> dict | None:
        """查询子代理当前状态。"""
        with self._lock:
            record = self._records.get(agent_id)
        if not record:
            return None
        return record.to_dict()

    def wait(self, agent_id: str, timeout: float | None = None) -> dict | None:
        """阻塞等待子代理完成。"""
        start = time.time()
        while True:
            result = self.get_result(agent_id)
            if not result:
                return None
            if result['status'] in ('completed', 'failed', 'cancelled'):
                return result
            if timeout and (time.time() - start) > timeout:
                return result  # 返回当前状态（可能仍是 running）
            time.sleep(0.5)

    def cancel(self, agent_id: str) -> bool:
        """取消子代理。只能标记状态，不能真正杀死线程。"""
        with self._lock:
            record = self._records.get(agent_id)
            if not record or record.status != SubAgentStatus.RUNNING:
                return False
            record.status = SubAgentStatus.CANCELLED
            record.completed_at = time.time()
            self._running_count -= 1
        if self._session_dir:
            self._save_record(record)
        return True

    def list_agents(self) -> list[dict]:
        """列出所有子代理。"""
        with self._lock:
            return [r.to_dict() for r in self._records.values()]

    def consume_completions(self) -> list[SubAgentRecord]:
        """
        消费本轮新完成的子代理（去重）。
        返回已完成但尚未被父代理处理的记录，并标记为已消费。
        """
        completed = []
        with self._lock:
            for record in self._records.values():
                if record.status in (SubAgentStatus.COMPLETED, SubAgentStatus.FAILED):
                    if record.agent_id not in self._polled_ids:
                        completed.append(record)
                        self._polled_ids.add(record.agent_id)
        return completed

    def poll_completions(self) -> list[SubAgentRecord]:
        """
        轮询本轮新完成的子代理。
        返回已完成但父代理尚未处理的记录。
        """
        completed = []
        with self._lock:
            for record in self._records.values():
                if record.status in (SubAgentStatus.COMPLETED, SubAgentStatus.FAILED):
                    completed.append(record)
        return completed

    def get_running(self) -> list[dict]:
        """获取正在运行的子代理。"""
        with self._lock:
            return [
                r.to_dict()
                for r in self._records.values()
                if r.status == SubAgentStatus.RUNNING
            ]

    def _save_record(self, record: SubAgentRecord):
        """持久化单条记录到 session 目录。"""
        if not self._session_dir:
            return
        try:
            self._session_dir.mkdir(parents=True, exist_ok=True)
            path = self._session_dir / f'subagent_{record.agent_id}.json'
            path.write_text(
                json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        except Exception:
            pass

    def save_all(self):
        """保存所有记录。"""
        if not self._session_dir:
            return
        for record in self._records.values():
            self._save_record(record)

    def shutdown(self):
        """关闭线程池。"""
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            self._executor.shutdown(wait=False)
