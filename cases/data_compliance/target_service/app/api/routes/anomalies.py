"""
异常规则与告警路由。

GET    /anomalies                    异常列表
GET    /anomalies/{id}               详情
POST   /anomalies/{id}/ack           确认
POST   /anomalies/{id}/resolve       解决
POST   /anomalies/{id}/ignore        忽略
GET    /anomalies/stats              聚合统计
GET    /anomalies/rules              规则列表
POST   /anomalies/rules              注册规则
POST   /anomalies/rules/{id}/enable
POST   /anomalies/rules/{id}/disable
POST   /anomalies/evaluate           手动扫描一批记录
GET    /anomalies/open/critical      最近紧急异常
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.repositories.anomaly_repository import AnomalyRepository
from app.repositories.instrument_repository import InstrumentRepository
from app.repositories.lab_result_repository import LabResultRepository
from app.services.anomaly_rule_engine import (
    AnomalyRuleEngine, load_default_rules,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_anomaly_repo: Optional[AnomalyRepository] = None
_engine: Optional[AnomalyRuleEngine] = None


def get_anomaly_repo() -> AnomalyRepository:
    global _anomaly_repo
    if _anomaly_repo is None:
        _anomaly_repo = AnomalyRepository()
    return _anomaly_repo


def get_engine() -> AnomalyRuleEngine:
    global _engine
    if _engine is None:
        # 注意：这里的 lab/instrument 用路由模块内的单例重新拼装；
        # 生产代码应通过 DI 容器共享同一套单例。
        from app.api.routes.lab_results import get_repo as _get_lab
        from app.api.routes.instruments import get_repo as _get_inst
        _engine = AnomalyRuleEngine(
            get_anomaly_repo(),
            lab_repo=_get_lab(),
            instrument_repo=_get_inst(),
        )
        load_default_rules(_engine)
    return _engine


def _reset_repo_for_tests() -> None:
    global _anomaly_repo, _engine
    _anomaly_repo = AnomalyRepository()
    _engine = None


class AckRequest(BaseModel):
    handler: str


class ResolveRequest(BaseModel):
    handler: str
    resolution_note: str


class IgnoreRequest(BaseModel):
    reason: str


class RuleConfig(BaseModel):
    rule_id: str
    name: str
    rule_type: str
    target_type: str
    severity: str = 'WARN'
    enabled: bool = True
    # 其余字段由各规则类型自定义
    extra: Dict[str, Any] = {}


class EvaluateBatchRequest(BaseModel):
    records: List[Dict[str, Any]]
    target_type: str = 'lab_result'


@router.get('')
def list_anomalies(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    rule_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    repo: AnomalyRepository = Depends(get_anomaly_repo),
) -> Dict[str, Any]:
    from app.repositories.base import Pagination, SortSpec
    pagination = Pagination(page=page, page_size=page_size)
    if target_type and target_id:
        items = repo.list_by_target(target_type, target_id)
    elif rule_id:
        items = repo.list_by_rule(rule_id, pagination=pagination)
    elif status in (None, 'open'):
        items = repo.list_open(severity=severity, pagination=pagination)
    else:
        filters: Dict[str, Any] = {'status': status}
        if severity:
            filters['severity'] = severity
        items = repo.list(
            filters=filters,
            sort=SortSpec('detected_at', 'desc'),
            pagination=pagination,
        )
    if pagination.total == 0:
        pagination.total = len(items)
    return {
        'total': pagination.total,
        'page': pagination.page,
        'page_size': pagination.page_size,
        'data': items,
    }


@router.get('/{anomaly_id}')
def get_anomaly(
    anomaly_id: str,
    repo: AnomalyRepository = Depends(get_anomaly_repo),
) -> Dict[str, Any]:
    a = repo.get_by_id(anomaly_id)
    if not a:
        raise HTTPException(status_code=404, detail='anomaly not found')
    return a


@router.post('/{anomaly_id}/ack')
def acknowledge_anomaly(
    anomaly_id: str,
    payload: AckRequest,
    repo: AnomalyRepository = Depends(get_anomaly_repo),
) -> Dict[str, Any]:
    try:
        return repo.acknowledge(anomaly_id, payload.handler)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/{anomaly_id}/resolve')
def resolve_anomaly(
    anomaly_id: str,
    payload: ResolveRequest,
    repo: AnomalyRepository = Depends(get_anomaly_repo),
) -> Dict[str, Any]:
    try:
        return repo.resolve(anomaly_id, payload.handler, payload.resolution_note)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/{anomaly_id}/ignore')
def ignore_anomaly(
    anomaly_id: str,
    payload: IgnoreRequest,
    repo: AnomalyRepository = Depends(get_anomaly_repo),
) -> Dict[str, Any]:
    try:
        return repo.ignore(anomaly_id, payload.reason)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get('/stats/summary')
def anomaly_stats(
    window_hours: int = Query(default=24, ge=1, le=720),
    repo: AnomalyRepository = Depends(get_anomaly_repo),
) -> Dict[str, Any]:
    return repo.statistics(window_hours=window_hours)


@router.get('/open/critical')
def recent_critical(
    hours: int = Query(default=24, ge=1, le=168),
    repo: AnomalyRepository = Depends(get_anomaly_repo),
) -> Dict[str, Any]:
    items = repo.list_recent_critical(hours=hours)
    return {'hours': hours, 'count': len(items), 'data': items}


@router.get('/rules/list')
def list_rules(
    target_type: Optional[str] = None,
    engine: AnomalyRuleEngine = Depends(get_engine),
) -> Dict[str, Any]:
    rules = engine.list_rules(target_type)
    return {
        'count': len(rules),
        'rules': [
            {
                'rule_id': r.rule_id,
                'name': r.name,
                'rule_type': r.rule_type,
                'target_type': r.target_type,
                'severity': r.severity,
                'enabled': r.enabled,
                'config': r.config,
            }
            for r in rules
        ],
    }


@router.post('/rules')
def register_rule(
    payload: RuleConfig,
    engine: AnomalyRuleEngine = Depends(get_engine),
) -> Dict[str, Any]:
    raw = {
        'rule_id': payload.rule_id,
        'name': payload.name,
        'rule_type': payload.rule_type,
        'target_type': payload.target_type,
        'severity': payload.severity,
        'enabled': payload.enabled,
        **(payload.extra or {}),
    }
    try:
        engine.load_from_config([raw])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {'rule_id': payload.rule_id, 'registered': True}


@router.post('/rules/{rule_id}/enable')
def enable_rule(
    rule_id: str,
    engine: AnomalyRuleEngine = Depends(get_engine),
) -> Dict[str, Any]:
    ok = engine.enable_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail='rule not found')
    return {'rule_id': rule_id, 'enabled': True}


@router.post('/rules/{rule_id}/disable')
def disable_rule(
    rule_id: str,
    engine: AnomalyRuleEngine = Depends(get_engine),
) -> Dict[str, Any]:
    ok = engine.disable_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail='rule not found')
    return {'rule_id': rule_id, 'enabled': False}


@router.post('/evaluate_batch')
def evaluate_batch(
    payload: EvaluateBatchRequest,
    engine: AnomalyRuleEngine = Depends(get_engine),
) -> Dict[str, Any]:
    summary = engine.evaluate_batch(payload.records, payload.target_type)
    return summary
