"""
异常扫描任务。

由 Scheduler 周期触发，扫描 LabResultRepository 和 InstrumentRepository，
把命中的异常灌进 AnomalyRuleEngine，由引擎写入 AnomalyRepository，
并通过 AnomalyNotifier 分发告警。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.repositories.instrument_repository import InstrumentRepository
from app.repositories.lab_result_repository import LabResultRepository
from app.services.anomaly_notifier import AnomalyNotifier
from app.services.anomaly_rule_engine import AnomalyRuleEngine

logger = logging.getLogger(__name__)


@dataclass
class AnomalyScanConfig:
    """扫描任务配置。"""
    lookback_hours: int = 24  # 仅扫描最近 N 小时的 lab_result
    scan_instruments: bool = True
    max_records_per_run: int = 50_000
    dispatch_notifications: bool = True


class AnomalyScanTask:
    """
    异常扫描任务。

    run() 方法被 Scheduler 周期性调用，执行一次完整的扫描。
    """

    def __init__(
        self,
        lab_repo: LabResultRepository,
        instrument_repo: InstrumentRepository,
        rule_engine: AnomalyRuleEngine,
        notifier: Optional[AnomalyNotifier] = None,
        config: Optional[AnomalyScanConfig] = None,
    ):
        self.lab_repo = lab_repo
        self.instrument_repo = instrument_repo
        self.rule_engine = rule_engine
        self.notifier = notifier
        self.config = config or AnomalyScanConfig()
        self._last_run_summary: Optional[Dict[str, Any]] = None
        self._run_count: int = 0

    def run(self) -> Dict[str, Any]:
        """执行一次扫描。返回扫描摘要。"""
        start = datetime.now()
        self._run_count += 1
        summary: Dict[str, Any] = {
            'run_at': start.isoformat(),
            'run_index': self._run_count,
            'lab_result': {},
            'instrument': {},
            'notifications': {},
        }

        # 1. 扫描 lab_result
        if self.lab_repo:
            summary['lab_result'] = self._scan_lab_results()

        # 2. 扫描 instrument
        if self.config.scan_instruments and self.instrument_repo:
            summary['instrument'] = self._scan_instruments()

        # 3. 分发告警
        if self.config.dispatch_notifications and self.notifier:
            triggered = (
                summary['lab_result'].get('triggered', 0)
                + summary['instrument'].get('triggered', 0)
            )
            summary['notifications'] = {
                'total_dispatched': triggered,
                'stats': self.notifier.statistics(),
            }

        duration = (datetime.now() - start).total_seconds()
        summary['duration_seconds'] = round(duration, 3)
        self._last_run_summary = summary
        logger.info('anomaly scan #%d completed in %.2fs: %s',
                     self._run_count, duration,
                     {k: summary[k].get('triggered', 0)
                      for k in ('lab_result', 'instrument')})
        return summary

    def _scan_lab_results(self) -> Dict[str, Any]:
        cutoff = datetime.now() - timedelta(hours=self.config.lookback_hours)
        # 取所有 lab_result，按 cutoff 过滤
        records = self.lab_repo.list()
        scanned_records = []
        for r in records:
            visit = r.get('visit_date')
            if isinstance(visit, datetime) and visit >= cutoff:
                scanned_records.append(r)
            elif isinstance(visit, str):
                try:
                    dt = datetime.fromisoformat(visit.replace(' ', 'T').rstrip('Z'))
                    if dt >= cutoff:
                        scanned_records.append(r)
                except Exception:
                    continue
            if len(scanned_records) >= self.config.max_records_per_run:
                break
        logger.info('scanning %d lab_results (lookback=%dh)',
                     len(scanned_records), self.config.lookback_hours)
        return self.rule_engine.evaluate_batch(scanned_records, 'lab_result')

    def _scan_instruments(self) -> Dict[str, Any]:
        records = self.instrument_repo.list()
        logger.info('scanning %d instruments', len(records))
        return self.rule_engine.evaluate_batch(records, 'instrument')

    def last_summary(self) -> Optional[Dict[str, Any]]:
        return self._last_run_summary

    def run_count(self) -> int:
        return self._run_count
