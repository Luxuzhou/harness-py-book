"""
审计日志仓储。

承担合规审计日志的持久化（JSONL 落盘）与查询。
与 AuditLogMiddleware 配合使用：中间件把每次 HTTP 请求写入 Repository，
Repository 把记录落地到 `audit_logs/*.jsonl`。
"""

from __future__ import annotations

import itertools
import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.repositories.base import BaseRepository, Pagination, SortSpec

logger = logging.getLogger(__name__)

# 全局单调计数器：把 audit_id 里的时间戳和一个进程内唯一后缀拼起来，
# 规避 datetime.now() 在 Windows 上只有毫秒精度（高频写入会让微秒位
# 撞成同一个时间戳，从而触发 DuplicateKeyError）。
_AUDIT_ID_COUNTER = itertools.count()
_AUDIT_ID_LOCK = threading.Lock()


def _next_audit_id() -> str:
    with _AUDIT_ID_LOCK:
        seq = next(_AUDIT_ID_COUNTER)
    return f'AUDIT-{datetime.now().strftime("%Y%m%d%H%M%S%f")}-{seq:08d}'


class AuditRepository(BaseRepository[Dict[str, Any]]):
    """
    审计记录仓储。

    记录字段：
    - audit_id (主键)
    - timestamp
    - user (可匿名)
    - request_id
    - method / path / status_code / duration_ms
    - client_ip
    - request_hash (请求体哈希，用于判重)
    - response_size
    - event_type (http_request / data_access / data_export / auth_event 等)
    - metadata (业务相关附加字段)
    """

    def __init__(
        self,
        initial: Optional[List[Dict[str, Any]]] = None,
        log_dir: Optional[Path] = None,
    ):
        super().__init__(initial)
        self.log_dir = log_dir
        self._file_lock = threading.Lock()
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)

    def primary_key(self) -> str:
        return 'audit_id'

    def indexed_fields(self) -> List[str]:
        return ['audit_id', 'user', 'request_id', 'event_type']

    # --- 落盘 ---

    def _current_log_file(self) -> Optional[Path]:
        if not self.log_dir:
            return None
        return self.log_dir / f'audit-{datetime.now().strftime("%Y-%m-%d")}.jsonl'

    def _persist(self, record: Dict[str, Any]) -> None:
        path = self._current_log_file()
        if not path:
            return
        with self._file_lock:
            try:
                with path.open('a', encoding='utf-8') as f:
                    json.dump(record, f, ensure_ascii=False, default=str)
                    f.write('\n')
            except OSError as e:
                logger.warning('audit persist failed: %s', e)

    def record_http(
        self,
        *,
        user: Optional[str],
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: int,
        client_ip: str,
        response_size: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entry = {
            'audit_id': _next_audit_id(),
            'timestamp': datetime.now().isoformat(),
            'event_type': 'http_request',
            'user': user or 'anonymous',
            'request_id': request_id,
            'method': method,
            'path': path,
            'status_code': status_code,
            'duration_ms': duration_ms,
            'client_ip': client_ip,
            'response_size': response_size,
            'metadata': metadata or {},
        }
        self.create(entry)
        self._persist(entry)
        return entry

    def record_data_access(
        self,
        *,
        user: Optional[str],
        request_id: str,
        target_type: str,
        target_id: str,
        action: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entry = {
            'audit_id': _next_audit_id(),
            'timestamp': datetime.now().isoformat(),
            'event_type': 'data_access',
            'user': user or 'anonymous',
            'request_id': request_id,
            'target_type': target_type,
            'target_id': target_id,
            'action': action,
            'metadata': metadata or {},
        }
        self.create(entry)
        self._persist(entry)
        return entry

    def record_data_export(
        self,
        *,
        user: Optional[str],
        request_id: str,
        export_format: str,
        record_count: int,
        filters: Dict[str, Any],
        output_path: str,
    ) -> Dict[str, Any]:
        entry = {
            'audit_id': _next_audit_id(),
            'timestamp': datetime.now().isoformat(),
            'event_type': 'data_export',
            'user': user or 'anonymous',
            'request_id': request_id,
            'export_format': export_format,
            'record_count': record_count,
            'filters': filters,
            'output_path': output_path,
        }
        self.create(entry)
        self._persist(entry)
        return entry

    def record_auth_event(
        self,
        *,
        user: Optional[str],
        event: str,  # login_success / login_failed / logout / token_expired
        client_ip: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entry = {
            'audit_id': _next_audit_id(),
            'timestamp': datetime.now().isoformat(),
            'event_type': 'auth_event',
            'user': user,
            'event': event,
            'client_ip': client_ip,
            'metadata': metadata or {},
        }
        self.create(entry)
        self._persist(entry)
        return entry

    # --- 查询 ---

    def search(
        self,
        *,
        user: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        pagination: Optional[Pagination] = None,
    ) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {}
        if user:
            filters['user'] = user
        if event_type:
            filters['event_type'] = event_type
        if since or until:
            def in_range(ts: Any) -> bool:
                if not isinstance(ts, str):
                    return False
                try:
                    dt = datetime.fromisoformat(ts)
                except Exception:
                    return False
                if since and dt < since:
                    return False
                if until and dt > until:
                    return False
                return True
            filters['timestamp'] = in_range
        return self.list(
            filters=filters,
            sort=SortSpec('timestamp', 'desc'),
            pagination=pagination,
        )

    def summary(self, window_hours: int = 24) -> Dict[str, Any]:
        cutoff = datetime.now() - timedelta(hours=window_hours)
        recent = [
            it for it in self.list()
            if isinstance(it.get('timestamp'), str)
               and self._parse_iso(it['timestamp']) is not None
               and self._parse_iso(it['timestamp']) >= cutoff
        ]
        by_type: Dict[str, int] = {}
        by_user: Dict[str, int] = {}
        by_status: Dict[int, int] = {}
        for it in recent:
            by_type[it.get('event_type', 'unknown')] = by_type.get(
                it.get('event_type', 'unknown'), 0) + 1
            u = it.get('user', 'anonymous')
            by_user[u] = by_user.get(u, 0) + 1
            sc = it.get('status_code')
            if isinstance(sc, int):
                by_status[sc] = by_status.get(sc, 0) + 1
        return {
            'window_hours': window_hours,
            'total_records': len(recent),
            'by_event_type': by_type,
            'top_users': dict(sorted(by_user.items(), key=lambda x: -x[1])[:10]),
            'by_status_code': by_status,
        }

    @staticmethod
    def _parse_iso(s: Any) -> Optional[datetime]:
        if not isinstance(s, str):
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
