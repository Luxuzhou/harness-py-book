"""
系统管理路由。

POST /admin/reload            触发数据刷新任务
POST /admin/scan/anomalies    手动触发异常扫描
POST /admin/reports/generate  手动触发报表生成
GET  /admin/health            完整健康检查（包含 repo 状态）
GET  /admin/stats             系统级聚合统计
GET  /admin/audit/summary     审计摘要
GET  /admin/scheduler/tasks   当前调度任务
POST /admin/scheduler/tasks/{id}/pause
POST /admin/scheduler/tasks/{id}/resume
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.routes.anomalies import get_anomaly_repo, get_engine
from app.api.routes.instruments import get_repo as get_instrument_repo
from app.api.routes.lab_results import get_repo as get_lab_repo
from app.api.routes.patients import get_repo as get_patient_repo
from app.repositories.audit_repository import AuditRepository
from app.services.anomaly_notifier import AnomalyNotifier
from app.services.scheduler import Scheduler
from app.services.tasks.anomaly_scan import AnomalyScanTask, AnomalyScanConfig
from app.services.tasks.data_refresh import DataRefreshTask, DataRefreshConfig
from app.services.tasks.report_generation import (
    ReportGenerationTask, ReportGenerationConfig,
)

logger = logging.getLogger(__name__)
router = APIRouter()


_start_time = time.time()

_audit_repo: Optional[AuditRepository] = None
_notifier: Optional[AnomalyNotifier] = None
_scheduler: Optional[Scheduler] = None


def get_audit_repo() -> AuditRepository:
    global _audit_repo
    if _audit_repo is None:
        base = Path(__file__).resolve().parents[3]
        _audit_repo = AuditRepository(log_dir=base / 'audit_logs')
    return _audit_repo


def get_notifier() -> AnomalyNotifier:
    global _notifier
    if _notifier is None:
        base = Path(__file__).resolve().parents[3]
        _notifier = AnomalyNotifier(log_dir=base / 'notifications')
    return _notifier


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler


def _reset_repo_for_tests() -> None:
    global _audit_repo, _notifier, _scheduler
    _audit_repo = None
    if _scheduler:
        _scheduler.stop()
    _scheduler = None
    _notifier = None


@router.post('/reload')
def trigger_reload(
    data_dir: str = Query(default='sample_data'),
    full_reload: bool = Query(default=False),
) -> Dict[str, Any]:
    task = DataRefreshTask(
        patient_repo=get_patient_repo(),
        lab_repo=get_lab_repo(),
        instrument_repo=get_instrument_repo(),
        config=DataRefreshConfig(data_dir=Path(data_dir), full_reload=full_reload),
    )
    try:
        return task.run()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'reload failed: {e}')


@router.post('/scan/anomalies')
def trigger_anomaly_scan(
    lookback_hours: int = Query(default=24, ge=1, le=24 * 30),
) -> Dict[str, Any]:
    scan = AnomalyScanTask(
        lab_repo=get_lab_repo(),
        instrument_repo=get_instrument_repo(),
        rule_engine=get_engine(),
        notifier=get_notifier(),
        config=AnomalyScanConfig(lookback_hours=lookback_hours),
    )
    return scan.run()


@router.post('/reports/generate')
def trigger_report(
    period: str = Query(default='daily'),
) -> Dict[str, Any]:
    base = Path(__file__).resolve().parents[3]
    task = ReportGenerationTask(
        patient_repo=get_patient_repo(),
        lab_repo=get_lab_repo(),
        instrument_repo=get_instrument_repo(),
        anomaly_repo=get_anomaly_repo(),
        audit_repo=get_audit_repo(),
        config=ReportGenerationConfig(
            output_dir=base / 'reports',
            period=period,
        ),
    )
    return task.run()


@router.get('/health')
def full_health() -> Dict[str, Any]:
    uptime = round(time.time() - _start_time, 2)
    return {
        'status': 'ok',
        'uptime_seconds': uptime,
        'patients_loaded': get_patient_repo().count(),
        'lab_results_loaded': get_lab_repo().count(),
        'instruments_loaded': get_instrument_repo().count(),
        'active_anomalies': len(get_anomaly_repo().list_open()),
        'rules_loaded': len(get_engine().list_rules()),
        'scheduler_task_count': len(get_scheduler().list_tasks()),
    }


@router.get('/stats')
def system_stats() -> Dict[str, Any]:
    return {
        'patients': get_patient_repo().statistics(),
        'lab_results': {
            'total': get_lab_repo().count(),
        },
        'instruments': get_instrument_repo().capacity_summary(),
        'anomalies': get_anomaly_repo().statistics(window_hours=24 * 7),
    }


@router.get('/audit/summary')
def audit_summary(
    window_hours: int = Query(default=24, ge=1, le=720),
) -> Dict[str, Any]:
    repo = get_audit_repo()
    return repo.summary(window_hours=window_hours)


@router.get('/scheduler/tasks')
def list_scheduler_tasks() -> Dict[str, Any]:
    sc = get_scheduler()
    return {'count': len(sc.list_tasks()), 'tasks': sc.list_tasks(),
            'recent_runs': sc.recent_runs(limit=20)}


@router.post('/scheduler/tasks/{task_id}/pause')
def pause_scheduler_task(task_id: str) -> Dict[str, Any]:
    sc = get_scheduler()
    if not sc.pause(task_id):
        raise HTTPException(status_code=404, detail='task not found')
    return {'task_id': task_id, 'paused': True}


@router.post('/scheduler/tasks/{task_id}/resume')
def resume_scheduler_task(task_id: str) -> Dict[str, Any]:
    sc = get_scheduler()
    if not sc.resume(task_id):
        raise HTTPException(status_code=404, detail='task not found')
    return {'task_id': task_id, 'resumed': True}
