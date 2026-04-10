"""
会话持久化
==========
jsonl格式，对齐Claude Code的session存储。
每个事件实时写入，支持断点恢复。
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path


class SessionWriter:
    """Session写入器。每条消息实时追加到jsonl。"""

    def __init__(self, session_id: str, session_dir: Path, cwd: Path):
        self.session_id = session_id
        self.session_dir = session_dir
        self.cwd = cwd
        self._path = session_dir / f'{session_id}.jsonl'
        self._lock = threading.Lock()
        session_dir.mkdir(parents=True, exist_ok=True)

        self._write_event({
            'type': 'session_start',
            'session_id': session_id,
            'cwd': str(cwd),
        })

    def write_message(self, role: str, content: str):
        self._write_event({
            'type': 'message',
            'role': role,
            'content': content[:5000],
        })

    def write_tool_call(self, tool_name: str, args: dict, ok: bool, result: str):
        self._write_event({
            'type': 'tool_call',
            'tool': tool_name,
            'args': {k: str(v)[:200] for k, v in args.items()},
            'ok': ok,
            'result_preview': result[:200],
        })

    def write_event(self, event: dict):
        self._write_event(event)

    def close(self, result: dict):
        self._write_event({
            'type': 'session_end',
            **{k: v for k, v in result.items() if not isinstance(v, (list, dict)) or k == 'cost_summary'},
        })

    def _write_event(self, event: dict):
        event['timestamp'] = time.time()
        try:
            with self._lock:
                with open(self._path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(event, ensure_ascii=False, default=str) + '\n')
        except OSError:
            pass


def load_session_messages(session_id: str, session_dir: Path) -> list[dict]:
    """从jsonl加载会话消息。"""
    path = session_dir / f'{session_id}.jsonl'
    if not path.exists():
        return []

    messages = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            event = json.loads(line)
            if event.get('type') == 'message':
                messages.append({
                    'role': event['role'],
                    'content': event.get('content', ''),
                })
        except json.JSONDecodeError:
            continue
    return messages


def list_sessions(session_dir: Path) -> list[tuple[str, float, int]]:
    results = []
    if not session_dir.exists():
        return results

    for path in sorted(session_dir.glob('*.jsonl'), key=lambda p: -p.stat().st_mtime):
        stat = path.stat()
        with open(path, 'r', encoding='utf-8') as f:
            count = sum(1 for _ in f)
        results.append((path.stem, stat.st_mtime, count))
    return results
