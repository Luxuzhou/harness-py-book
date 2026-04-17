"""
报表生成任务。

周期性生成日报 / 周报 / 月报，落盘到 `reports/` 目录。
报表涵盖：
- 患者画像总览
- 检验量统计
- 异常率趋势
- 仪器负载
- 合规审计摘要
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.repositories.anomaly_repository import AnomalyRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.instrument_repository import InstrumentRepository
from app.repositories.lab_result_repository import LabResultRepository
from app.repositories.patient_repository import PatientRepository

logger = logging.getLogger(__name__)


@dataclass
class ReportGenerationConfig:
    """报表生成配置。"""
    output_dir: Path = Path('reports')
    period: str = 'daily'  # daily / weekly / monthly
    include_raw_json: bool = True
    include_markdown: bool = True
    retention_days: int = 90  # 历史报表保留天数


class ReportGenerationTask:
    """
    报表生成任务。

    run() 生成本周期的报表文件，返回摘要。
    """

    def __init__(
        self,
        patient_repo: PatientRepository,
        lab_repo: LabResultRepository,
        instrument_repo: InstrumentRepository,
        anomaly_repo: AnomalyRepository,
        audit_repo: Optional[AuditRepository] = None,
        config: Optional[ReportGenerationConfig] = None,
    ):
        self.patient_repo = patient_repo
        self.lab_repo = lab_repo
        self.instrument_repo = instrument_repo
        self.anomaly_repo = anomaly_repo
        self.audit_repo = audit_repo
        self.config = config or ReportGenerationConfig()
        self._last_output_paths: List[Path] = []
        self._run_count = 0

    def run(self) -> Dict[str, Any]:
        self._run_count += 1
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        generated_at = datetime.now()
        report = self._build_report(generated_at)

        summary: Dict[str, Any] = {
            'run_at': generated_at.isoformat(),
            'run_index': self._run_count,
            'period': self.config.period,
            'files': [],
        }

        if self.config.include_raw_json:
            p = self._write_json(report, generated_at)
            summary['files'].append(str(p))
        if self.config.include_markdown:
            p = self._write_markdown(report, generated_at)
            summary['files'].append(str(p))

        self._last_output_paths = [Path(f) for f in summary['files']]
        # 清理过期报表
        removed = self._cleanup_old_reports()
        summary['removed_old_reports'] = removed

        logger.info('report #%d generated: %s', self._run_count, summary['files'])
        return summary

    # --- 报表内容 ---

    def _build_report(self, now: datetime) -> Dict[str, Any]:
        window = self._window_for_period(now)
        return {
            'generated_at': now.isoformat(),
            'period': self.config.period,
            'window_start': window[0].isoformat(),
            'window_end': window[1].isoformat(),
            'patient_overview': self._patient_overview(),
            'lab_result_summary': self._lab_summary(),
            'anomaly_summary': self._anomaly_summary(),
            'instrument_summary': self._instrument_summary(),
            'audit_summary': self._audit_summary(),
        }

    def _patient_overview(self) -> Dict[str, Any]:
        return self.patient_repo.statistics()

    def _lab_summary(self) -> Dict[str, Any]:
        try:
            daily = self.lab_repo.daily_volume(days=7)
        except Exception:
            daily = []
        try:
            top_inst = self.lab_repo.top_instruments_by_volume(top_n=10)
        except Exception:
            top_inst = []
        return {
            'total_results': self.lab_repo.count(),
            'daily_volume_7d': daily,
            'top_instruments_by_volume': top_inst,
        }

    def _anomaly_summary(self) -> Dict[str, Any]:
        return self.anomaly_repo.statistics(window_hours=24 * 7)

    def _instrument_summary(self) -> Dict[str, Any]:
        cap = self.instrument_repo.capacity_summary()
        due = self.instrument_repo.find_due_calibration(days_ahead=14)
        overdue = self.instrument_repo.find_overdue_calibration()
        return {
            **cap,
            'due_calibration_in_14d': len(due),
            'overdue_calibration': len(overdue),
        }

    def _audit_summary(self) -> Dict[str, Any]:
        if self.audit_repo:
            return self.audit_repo.summary(window_hours=24)
        return {'disabled': True}

    def _window_for_period(self, now: datetime) -> tuple:
        if self.config.period == 'weekly':
            return (now - timedelta(days=7), now)
        if self.config.period == 'monthly':
            return (now - timedelta(days=30), now)
        return (now - timedelta(days=1), now)

    # --- 输出 ---

    def _write_json(self, report: Dict[str, Any], now: datetime) -> Path:
        stamp = now.strftime('%Y%m%d_%H%M%S')
        path = self.config.output_dir / f'{self.config.period}-{stamp}.json'
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding='utf-8',
        )
        return path

    def _write_markdown(self, report: Dict[str, Any], now: datetime) -> Path:
        stamp = now.strftime('%Y%m%d_%H%M%S')
        path = self.config.output_dir / f'{self.config.period}-{stamp}.md'
        lines: List[str] = []
        lines.append(f'# {self.config.period.capitalize()} 报表')
        lines.append(f'生成时间：{report["generated_at"]}')
        lines.append(f'统计窗口：{report["window_start"]} ~ {report["window_end"]}')
        lines.append('')
        lines.append('## 患者画像')
        po = report['patient_overview']
        lines.append(f'- 总患者数：{po.get("total", 0)}')
        lines.append(f'- 平均年龄：{po.get("avg_age")}')
        if po.get('age_distribution'):
            for bucket, cnt in po['age_distribution'].items():
                lines.append(f'  - {bucket} 岁：{cnt}')
        lines.append('')

        lines.append('## 检验量')
        ls = report['lab_result_summary']
        lines.append(f'- 总检验量：{ls.get("total_results", 0)}')
        lines.append('- 最近 7 天每日检验量：')
        for date_str, count in ls.get('daily_volume_7d', []):
            lines.append(f'  - {date_str}: {count}')
        lines.append('')

        lines.append('## 异常情况')
        an = report['anomaly_summary']
        lines.append(f'- 异常总数：{an.get("total", 0)}')
        lines.append(f'- 窗口内异常：{an.get("in_window_total", 0)}')
        lines.append('- 按严重度：' + str(an.get('by_severity', {})))
        lines.append('- 平均修复时长（小时）：' + str(
            an.get('mean_time_to_resolve_hours', 'N/A')))
        lines.append('')

        lines.append('## 仪器状态')
        ins = report['instrument_summary']
        lines.append(f'- 仪器总数：{ins.get("total", 0)}')
        lines.append(f'- 在线：{ins.get("online", 0)}')
        lines.append(f'- 14 天内到期：{ins.get("due_calibration_in_14d", 0)}')
        lines.append(f'- 已过期未校准：{ins.get("overdue_calibration", 0)}')
        lines.append('')

        lines.append('## 审计摘要')
        au = report['audit_summary']
        if au.get('disabled'):
            lines.append('- 审计仓储未配置')
        else:
            lines.append(f'- 审计记录数（24h）：{au.get("total_records", 0)}')
            lines.append(f'- 按事件类型：{au.get("by_event_type", {})}')

        path.write_text('\n'.join(lines), encoding='utf-8')
        return path

    # --- 保留策略 ---

    def _cleanup_old_reports(self) -> int:
        cutoff = datetime.now() - timedelta(days=self.config.retention_days)
        removed = 0
        if not self.config.output_dir.exists():
            return 0
        for f in self.config.output_dir.iterdir():
            if not f.is_file():
                continue
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                continue
        return removed

    def last_output_paths(self) -> List[Path]:
        return list(self._last_output_paths)
