"""
Session持久化：jsonl追加写入（对齐Claude Code格式）
====================================================
Ch6记忆层的持久化组件。崩溃安全、实时可观察。
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return uuid4().hex


def _git_branch(cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                           capture_output=True, text=True, timeout=5, cwd=str(cwd) if cwd else None)
        return r.stdout.strip() if r.returncode == 0 else ''
    except Exception:
        return ''


class SessionWriter:
    """jsonl追加写入器。每条事件立即写入磁盘。"""

    def __init__(self, session_id: str, directory: Path, cwd: Path | None = None):
        self.session_id = session_id
        self.directory = directory
        self.cwd = cwd or Path.cwd()
        self._path = directory / f'{session_id}.jsonl'
        self._branch = _git_branch(cwd)
        self._prev_uuid: str | None = None
        directory.mkdir(parents=True, exist_ok=True)

        # 写入session开始事件
        self._write({'type': 'permission-mode', 'permissionMode': 'auto'})

    def write_message(self, role: str, content: str, **extra) -> str:
        """写入一条消息事件。返回uuid。"""
        msg_uuid = _uuid()

        # Claude Code格式：type就是角色名
        event_type = 'tool_result' if role == 'tool' else role
        event = {
            'parentUuid': self._prev_uuid,
            'isSidechain': False,
            'type': event_type,
            'message': {'role': role, 'content': content, **extra},
            'uuid': msg_uuid,
            'timestamp': _now(),
            'cwd': str(self.cwd),
            'sessionId': self.session_id,
            'version': 'harness-py/0.1.0',
            'gitBranch': self._branch,
        }
        if role == 'user':
            event['promptId'] = _uuid()

        self._write(event)
        self._prev_uuid = msg_uuid
        return msg_uuid

    def write_event(self, event: dict) -> None:
        """写入一条自定义事件。"""
        event.setdefault('timestamp', _now())
        event.setdefault('sessionId', self.session_id)
        self._write(event)

    def _write(self, event: dict) -> None:
        with open(self._path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')


def load_session_messages(session_id: str, directory: Path) -> list[dict]:
    """从jsonl重建消息列表（事件重放）。"""
    path = directory / f'{session_id}.jsonl'
    if not path.exists():
        return []

    message_types = {'user', 'assistant', 'system', 'tool_result'}
    messages = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('type') in message_types:
                msg = event.get('message', {})
                if isinstance(msg, dict):
                    messages.append(msg)
    return messages


def list_sessions(directory: Path) -> list[tuple[str, float, int]]:
    """列出所有session。返回 [(session_id, mtime, event_count)]。"""
    results = []
    if not directory.exists():
        return results
    for path in sorted(directory.glob('*.jsonl'), key=lambda p: -p.stat().st_mtime):
        sid = path.stem
        mtime = path.stat().st_mtime
        with open(path, 'r', encoding='utf-8') as f:
            count = sum(1 for _ in f)
        results.append((sid, mtime, count))
    return results
