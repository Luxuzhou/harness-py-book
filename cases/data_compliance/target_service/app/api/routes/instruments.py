"""
仪器管理路由。

GET    /instruments                  列表
GET    /instruments/{id}             详情
POST   /instruments                  创建
PATCH  /instruments/{id}             更新
DELETE /instruments/{id}             软删除
POST   /instruments/{id}/offline     标记离线
POST   /instruments/{id}/online      标记上线
POST   /instruments/{id}/calibration 记录校准
GET    /instruments/alerts/due       即将到期仪器
GET    /instruments/alerts/overdue   已过期仪器
GET    /instruments/stats/capacity   产能摘要
GET    /instruments/search/supporting_test/{code}
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.repositories.base import Pagination
from app.repositories.instrument_repository import InstrumentRepository

logger = logging.getLogger(__name__)
router = APIRouter()

_repo: Optional[InstrumentRepository] = None


def get_repo() -> InstrumentRepository:
    global _repo
    if _repo is None:
        _repo = InstrumentRepository()
    return _repo


def _reset_repo_for_tests() -> None:
    global _repo
    _repo = InstrumentRepository()


class InstrumentCreate(BaseModel):
    department_id: str
    name: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    status: str = 'online'
    last_calibration: Optional[str] = None
    next_calibration: Optional[str] = None
    supported_tests: Optional[str] = None
    daily_capacity: Optional[int] = Field(default=None, ge=0)


class InstrumentUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    supported_tests: Optional[str] = None
    daily_capacity: Optional[int] = Field(default=None, ge=0)


class OfflineRequest(BaseModel):
    reason: Optional[str] = None


class CalibrationRequest(BaseModel):
    calibration_date: date
    next_due_date: Optional[date] = None


@router.get('')
def list_instruments(
    status: Optional[str] = None,
    department: Optional[str] = None,
    manufacturer: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    pagination = Pagination(page=page, page_size=page_size)
    if status:
        items = repo.list_by_status(status)
    elif manufacturer:
        items = repo.list_by_manufacturer(manufacturer)
    elif department:
        items = repo.list_online(department)
    else:
        items = repo.list(pagination=pagination)
    if pagination.total == 0:
        pagination.total = len(items)
        items = pagination.slice(items)
    return {
        'total': pagination.total,
        'page': pagination.page,
        'page_size': pagination.page_size,
        'data': items,
    }


@router.get('/{instrument_id}')
def get_instrument(
    instrument_id: str,
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    it = repo.get_by_id(instrument_id)
    if not it:
        raise HTTPException(status_code=404, detail='instrument not found')
    return it


@router.post('')
def create_instrument(
    payload: InstrumentCreate,
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    try:
        return repo.create(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch('/{instrument_id}')
def update_instrument(
    instrument_id: str,
    payload: InstrumentUpdate,
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail='empty patch')
    try:
        return repo.update(instrument_id, patch)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete('/{instrument_id}')
def delete_instrument(
    instrument_id: str,
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    ok = repo.delete(instrument_id, soft=True)
    if not ok:
        raise HTTPException(status_code=404, detail='not found')
    return {'deleted': True, 'instrument_id': instrument_id}


@router.post('/{instrument_id}/offline')
def mark_offline(
    instrument_id: str,
    payload: OfflineRequest,
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    ok = repo.mark_offline(instrument_id, reason=payload.reason)
    if not ok:
        raise HTTPException(status_code=404, detail='not found')
    return {'instrument_id': instrument_id, 'status': 'offline',
            'reason': payload.reason}


@router.post('/{instrument_id}/online')
def mark_online(
    instrument_id: str,
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    ok = repo.mark_online(instrument_id)
    if not ok:
        raise HTTPException(status_code=404, detail='not found')
    return {'instrument_id': instrument_id, 'status': 'online'}


@router.post('/{instrument_id}/calibration')
def record_calibration(
    instrument_id: str,
    payload: CalibrationRequest,
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    ok = repo.record_calibration(
        instrument_id, payload.calibration_date, payload.next_due_date,
    )
    if not ok:
        raise HTTPException(status_code=404, detail='not found')
    return {'instrument_id': instrument_id,
            'calibration_date': payload.calibration_date.isoformat(),
            'next_due_date': (
                payload.next_due_date.isoformat() if payload.next_due_date else None)}


@router.get('/alerts/due')
def due_calibration(
    days_ahead: int = Query(default=7, ge=1, le=365),
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    items = repo.find_due_calibration(days_ahead=days_ahead)
    return {'days_ahead': days_ahead, 'count': len(items), 'data': items}


@router.get('/alerts/overdue')
def overdue_calibration(
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    items = repo.find_overdue_calibration()
    return {'count': len(items), 'data': items}


@router.get('/stats/capacity')
def capacity_summary(
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    return repo.capacity_summary()


@router.get('/search/supporting_test/{test_code}')
def find_supporting_test(
    test_code: str,
    repo: InstrumentRepository = Depends(get_repo),
) -> Dict[str, Any]:
    items = repo.list_supporting_test(test_code)
    return {'test_code': test_code, 'count': len(items), 'data': items}
