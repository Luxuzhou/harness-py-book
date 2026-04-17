"""
异常记录仓储。

承担异常规则、异常告警、异常历史的存储与查询。
异常记录的生命周期：NEW → ACKNOWLEDGED → RESOLVED / IGNORED。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.repositories.base import (
    BaseRepository, NotFoundError, Pagination, SortSpec,
)

logger = logging.getLogger(__name__)


class AnomalyRepository(BaseRepository[Dict[str, Any]]):
    """
    异常记录仓储。

    记录字段：
    - anomaly_id (主键, UUID)
    - rule_id (触发的规则 ID)
    - severity (INFO / WARN / CRIT)
    - status (NEW / ACKNOWLEDGED / RESOLVED / IGNORED)
    - target_type (lab_result / instrument / patient / pathway)
    - target_id
    - description
    - detected_at
    - acknowledged_at (可选)
    - resolved_at (可选)
    - handler (处理人)
    - resolution_note
    """

    STATUS_NEW = 'NEW'
    STATUS_ACK = 'ACKNOWLEDGED'
    STATUS_RESOLVED = 'RESOLVED'
    STATUS_IGNORED = 'IGNORED'
    VALID_STATUSES = {STATUS_NEW, STATUS_ACK, STATUS_RESOLVED, STATUS_IGNORED}

    SEVERITY_INFO = 'INFO'
    SEVERITY_WARN = 'WARN'
    SEVERITY_CRIT = 'CRIT'
    VALID_SEVERITIES = {SEVERITY_INFO, SEVERITY_WARN, SEVERITY_CRIT}

    def primary_key(self) -> str:
        return 'anomaly_id'

    def indexed_fields(self) -> List[str]:
        return ['anomaly_id', 'rule_id', 'target_id', 'status']

    # --- 业务动作 ---

    def open_anomaly(
        self,
        rule_id: str,
        target_type: str,
        target_id: str,
        severity: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建新的 NEW 状态异常。"""
        if severity not in self.VALID_SEVERITIES:
            raise ValueError(f'invalid severity: {severity}')
        record = {
            'anomaly_id': str(uuid.uuid4()),
            'rule_id': rule_id,
            'severity': severity,
            'status': self.STATUS_NEW,
            'target_type': target_type,
            'target_id': target_id,
            'description': description,
            'detected_at': datetime.now().isoformat(),
            'metadata': metadata or {},
        }
        return self.create(record)

    def acknowledge(self, anomaly_id: str, handler: str) -> Dict[str, Any]:
        patch = {
            'status': self.STATUS_ACK,
            'acknowledged_at': datetime.now().isoformat(),
            'handler': handler,
        }
        return self.update(anomaly_id, patch)

    def resolve(
        self,
        anomaly_id: str,
        handler: str,
        resolution_note: str,
    ) -> Dict[str, Any]:
        patch = {
            'status': self.STATUS_RESOLVED,
            'resolved_at': datetime.now().isoformat(),
            'handler': handler,
            'resolution_note': resolution_note,
        }
        return self.update(anomaly_id, patch)

    def ignore(self, anomaly_id: str, reason: str) -> Dict[str, Any]:
        patch = {
            'status': self.STATUS_IGNORED,
            'resolution_note': reason,
            'resolved_at': datetime.now().isoformat(),
        }
        return self.update(anomaly_id, patch)

    def bulk_ignore_by_rule(
        self,
        rule_id: str,
        reason: str,
    ) -> int:
        """批量忽略某规则的所有未处理异常。"""
        count = 0
        pending = self.list(filters={
            'rule_id': rule_id,
            'status': [self.STATUS_NEW, self.STATUS_ACK],
        })
        for it in pending:
            try:
                self.ignore(it['anomaly_id'], reason)
                count += 1
            except Exception as e:
                logger.warning('ignore failed for %s: %s', it['anomaly_id'], e)
        return count

    # --- 查询 ---

    def list_open(
        self,
        severity: Optional[str] = None,
        pagination: Optional[Pagination] = None,
    ) -> List[Dict[str, Any]]:
        """列出 NEW / ACKNOWLEDGED 的未闭环异常。"""
        filters: Dict[str, Any] = {
            'status': [self.STATUS_NEW, self.STATUS_ACK],
        }
        if severity:
            filters['severity'] = severity
        return self.list(
            filters=filters,
            sort=SortSpec('detected_at', 'desc'),
            pagination=pagination,
        )

    def list_by_target(
        self,
        target_type: str,
        target_id: str,
    ) -> List[Dict[str, Any]]:
        return self.list(
            filters={'target_type': target_type, 'target_id': target_id},
            sort=SortSpec('detected_at', 'desc'),
        )

    def list_by_rule(
        self,
        rule_id: str,
        pagination: Optional[Pagination] = None,
    ) -> List[Dict[str, Any]]:
        return self.list(
            filters={'rule_id': rule_id},
            sort=SortSpec('detected_at', 'desc'),
            pagination=pagination,
        )

    def list_recent_critical(
        self,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """最近 N 小时的 CRIT 级异常。"""
        cutoff = datetime.now() - timedelta(hours=hours)

        def recent(d: Any) -> bool:
            if isinstance(d, str):
                try:
                    return datetime.fromisoformat(d) >= cutoff
                except Exception:
                    return False
            return False

        return self.list(
            filters={'severity': self.SEVERITY_CRIT, 'detected_at': recent},
            sort=SortSpec('detected_at', 'desc'),
        )

    def statistics(self, window_hours: int = 24) -> Dict[str, Any]:
        """按状态、严重度、规则聚合统计。"""
        cutoff = datetime.now() - timedelta(hours=window_hours)

        def recent(d: Any) -> bool:
            if isinstance(d, str):
                try:
                    return datetime.fromisoformat(d) >= cutoff
                except Exception:
                    return False
            return False

        window = self.list(filters={'detected_at': recent})
        all_items = self.list()

        by_status: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_rule: Dict[str, int] = {}
        for it in all_items:
            by_status[it.get('status', 'UNK')] = by_status.get(
                it.get('status', 'UNK'), 0) + 1
            by_severity[it.get('severity', 'UNK')] = by_severity.get(
                it.get('severity', 'UNK'), 0) + 1
            rid = it.get('rule_id')
            if rid:
                by_rule[rid] = by_rule.get(rid, 0) + 1

        mttr = self._mean_time_to_resolve(all_items)

        return {
            'total': len(all_items),
            'in_window_total': len(window),
            'by_status': by_status,
            'by_severity': by_severity,
            'top_rules': dict(sorted(by_rule.items(), key=lambda x: -x[1])[:10]),
            'mean_time_to_resolve_hours': mttr,
        }

    def _mean_time_to_resolve(
        self,
        items: List[Dict[str, Any]],
    ) -> Optional[float]:
        deltas: List[float] = []
        for it in items:
            det = it.get('detected_at')
            rev = it.get('resolved_at')
            if not det or not rev:
                continue
            try:
                d1 = datetime.fromisoformat(det)
                d2 = datetime.fromisoformat(rev)
                deltas.append((d2 - d1).total_seconds() / 3600.0)
            except Exception:
                continue
        if not deltas:
            return None
        return round(sum(deltas) / len(deltas), 2)
