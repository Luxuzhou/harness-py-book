"""
检验结果路由。

GET    /lab_results                列表（按 patient / step_code / date_range 过滤）
GET    /lab_results/{result_id}    单条详情
POST   /lab_results                录入新结果
PATCH  /lab_results/{result_id}    更新
DELETE /lab_results/{result_id}    软删除
GET    /lab_results/stats/values   统计（mean/stdev/分位数）
GET    /lab_results/stats/daily    每日检验量
GET    /lab_results/stats/monthly  月度异常率
GET    /lab_results/stats/top_instruments
GET    /lab_results/outliers       k-sigma 异常值
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.repositories.base import Pagination, SortSpec
from app.repositories.lab_result_repository import LabResultRepository

logger = logging.getLogger(__name__)
router = APIRouter()

_repo: Optional[LabResultRepository] = None


def get_repo() -> LabResultRepository:
    global _repo
    if _repo is None:
        _repo = LabResultRepository()
    return _repo


def _reset_repo_for_tests() -> None:
    global _repo
    _repo = LabResultRepository()


class LabResultCreate(BaseModel):
    result_id: str
    patient_id: str
    step_code: str
    step_name: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    department_id: Optional[str] = None
    visit_date: Optional[datetime] = None
    flag: Optional[str] = None


class LabResultUpdate(BaseModel):
    step_name: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    flag: Optional[str] = None


@router.get('')
def list_results(
    patient_id: Optional[str] = None,
    step_code: Optional[str] = None,
    instrument_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    only_abnormal: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    repo: LabResultRepository = Depends(get_repo),
) -> Dict[str, Any]:
    pagination = Pagination(page=page, page_size=page_size)
    if only_abnormal:
        items = repo.list_abnormal(step_code=step_code, pagination=pagination)
    elif patient_id:
        items = repo.list_by_patient(patient_id, pagination=pagination)
    elif instrument_id:
        items = repo.list_by_instrument(instrument_id, pagination=pagination)
    elif start_date and end_date:
        items = repo.list_by_date_range(
            step_code, start_date, end_date, pagination=pagination,
        )
    elif step_code:
        items = repo.list_by_step_code(step_code, pagination=pagination)
    else:
        items = repo.list(
            sort=SortSpec('visit_date', 'desc'),
            pagination=pagination,
        )
    return {
        'total': pagination.total,
        'page': pagination.page,
        'page_size': pagination.page_size,
        'data': items,
    }


@router.get('/{result_id}')
def get_result(
    result_id: str,
    repo: LabResultRepository = Depends(get_repo),
) -> Dict[str, Any]:
    r = repo.get_by_id(result_id)
    if not r:
        raise HTTPException(status_code=404, detail='lab_result not found')
    return r


@router.post('')
def create_result(
    payload: LabResultCreate,
    repo: LabResultRepository = Depends(get_repo),
) -> Dict[str, Any]:
    try:
        created = repo.create(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return created


@router.patch('/{result_id}')
def update_result(
    result_id: str,
    payload: LabResultUpdate,
    repo: LabResultRepository = Depends(get_repo),
) -> Dict[str, Any]:
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail='empty patch')
    try:
        updated = repo.update(result_id, patch)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return updated


@router.delete('/{result_id}')
def delete_result(
    result_id: str,
    repo: LabResultRepository = Depends(get_repo),
) -> Dict[str, Any]:
    ok = repo.delete(result_id, soft=True)
    if not ok:
        raise HTTPException(status_code=404, detail='not found')
    return {'deleted': True, 'result_id': result_id}


@router.get('/stats/values')
def value_statistics(
    step_code: str,
    instrument_id: Optional[str] = None,
    repo: LabResultRepository = Depends(get_repo),
) -> Dict[str, Any]:
    return repo.value_statistics(step_code, instrument_id)


@router.get('/stats/daily')
def daily_volume(
    step_code: Optional[str] = None,
    days: int = Query(default=7, ge=1, le=90),
    repo: LabResultRepository = Depends(get_repo),
) -> Dict[str, Any]:
    series = repo.daily_volume(step_code=step_code, days=days)
    return {'step_code': step_code, 'days': days,
            'series': [{'date': d, 'count': c} for d, c in series]}


@router.get('/stats/monthly_abnormal')
def monthly_abnormal_rate(
    step_code: str,
    months: int = Query(default=6, ge=1, le=24),
    repo: LabResultRepository = Depends(get_repo),
) -> Dict[str, Any]:
    return {'step_code': step_code, 'months': months,
            'series': repo.monthly_abnormal_rate(step_code, months)}


@router.get('/stats/top_instruments')
def top_instruments(
    step_code: Optional[str] = None,
    top_n: int = Query(default=10, ge=1, le=100),
    repo: LabResultRepository = Depends(get_repo),
) -> Dict[str, Any]:
    tops = repo.top_instruments_by_volume(step_code=step_code, top_n=top_n)
    return {'step_code': step_code, 'top_n': top_n,
            'ranking': [{'instrument_id': i, 'volume': c} for i, c in tops]}


@router.get('/outliers')
def list_outliers(
    step_code: str,
    sigma: float = Query(default=3.0, ge=1.0, le=10.0),
    instrument_id: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    repo: LabResultRepository = Depends(get_repo),
) -> Dict[str, Any]:
    items = repo.outlier_detection(step_code, sigma, instrument_id)
    return {
        'step_code': step_code,
        'sigma': sigma,
        'instrument_id': instrument_id,
        'count': len(items),
        'outliers': items[:limit],
    }
