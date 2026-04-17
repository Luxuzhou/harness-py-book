"""
患者管理路由。

POST   /patients                  创建患者
GET    /patients                  列表（支持分页、过滤）
GET    /patients/{id}             获取单个患者（自动脱敏）
PATCH  /patients/{id}             更新
DELETE /patients/{id}             软删除
GET    /patients/statistics       统计摘要
POST   /patients/merge            合并重复患者
GET    /patients/search/by_id_card 按身份证号查找
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.repositories.base import Pagination, SortSpec
from app.repositories.patient_repository import PatientRepository

logger = logging.getLogger(__name__)
router = APIRouter()

# 模块级单例（生产场景通过依赖注入框架管理）
_repo: Optional[PatientRepository] = None


def get_repo() -> PatientRepository:
    global _repo
    if _repo is None:
        _repo = PatientRepository()
    return _repo


def _reset_repo_for_tests() -> None:
    """仅测试用：把模块级单例清空。"""
    global _repo
    _repo = PatientRepository()


class PatientCreate(BaseModel):
    patient_id: str
    name: str
    id_card: str
    gender: str
    age: int = Field(ge=0, le=150)
    department: Optional[str] = None
    diagnosis: Optional[str] = None
    phone: Optional[str] = None


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=150)
    department: Optional[str] = None
    diagnosis: Optional[str] = None
    phone: Optional[str] = None


class MergeRequest(BaseModel):
    survivor_id: str
    victim_id: str


def _mask_patient(p: Dict[str, Any]) -> Dict[str, Any]:
    """路由层的 PII 脱敏。生产场景调用 app.core.security.mask_pii。"""
    from copy import deepcopy
    masked = deepcopy(p)
    name = masked.get('name')
    if isinstance(name, str) and len(name) > 1:
        masked['name'] = name[0] + '*' * (len(name) - 1)
    ic = masked.get('id_card')
    if isinstance(ic, str) and len(ic) >= 10:
        masked['id_card'] = ic[:6] + '*' * (len(ic) - 10) + ic[-4:]
    phone = masked.get('phone')
    if isinstance(phone, str) and len(phone) >= 7:
        masked['phone'] = phone[:3] + '*' * (len(phone) - 7) + phone[-4:]
    return masked


@router.get('')
def list_patients(
    department: Optional[str] = None,
    min_age: Optional[int] = Query(default=None, ge=0),
    max_age: Optional[int] = Query(default=None, le=150),
    diagnosis_keyword: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    repo: PatientRepository = Depends(get_repo),
) -> Dict[str, Any]:
    pagination = Pagination(page=page, page_size=page_size)
    if diagnosis_keyword:
        items = repo.list_by_diagnosis_keywords(
            [diagnosis_keyword], pagination=pagination,
        )
    elif min_age is not None or max_age is not None:
        items = repo.list_by_age_range(
            min_age or 0, max_age or 150, pagination=pagination,
        )
    elif department:
        items = repo.list_by_department(department, pagination=pagination)
    else:
        items = repo.list(
            sort=SortSpec('patient_id'),
            pagination=pagination,
        )
    return {
        'total': pagination.total,
        'page': pagination.page,
        'page_size': pagination.page_size,
        'data': [_mask_patient(p) for p in items],
    }


@router.get('/{patient_id}')
def get_patient(
    patient_id: str,
    include_sensitive: bool = False,
    repo: PatientRepository = Depends(get_repo),
) -> Dict[str, Any]:
    """
    获取患者详情。

    include_sensitive=True 需要高权限角色，当前 MVP 实现仍然自动脱敏；
    合规改造阶段由 Agent 补上真正的角色校验。
    """
    p = repo.get_by_id(patient_id)
    if not p:
        raise HTTPException(status_code=404, detail=f'patient {patient_id} not found')
    return _mask_patient(p)


@router.post('')
def create_patient(
    payload: PatientCreate,
    repo: PatientRepository = Depends(get_repo),
) -> Dict[str, Any]:
    try:
        created = repo.create(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _mask_patient(created)


@router.patch('/{patient_id}')
def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    repo: PatientRepository = Depends(get_repo),
) -> Dict[str, Any]:
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail='empty patch')
    try:
        updated = repo.update(patient_id, patch)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _mask_patient(updated)


@router.delete('/{patient_id}')
def delete_patient(
    patient_id: str,
    repo: PatientRepository = Depends(get_repo),
) -> Dict[str, Any]:
    ok = repo.delete(patient_id, soft=True)
    if not ok:
        raise HTTPException(status_code=404, detail='not found')
    return {'deleted': True, 'patient_id': patient_id}


@router.get('/statistics/summary')
def patient_statistics(
    repo: PatientRepository = Depends(get_repo),
) -> Dict[str, Any]:
    return repo.statistics()


@router.post('/merge')
def merge_patients(
    payload: MergeRequest,
    repo: PatientRepository = Depends(get_repo),
) -> Dict[str, Any]:
    try:
        result = repo.merge_duplicate(payload.survivor_id, payload.victim_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {'merged_into': payload.survivor_id,
            'merged_from': payload.victim_id,
            'result': _mask_patient(result)}


@router.get('/search/by_id_card/{id_card}')
def find_by_id_card(
    id_card: str,
    repo: PatientRepository = Depends(get_repo),
) -> Dict[str, Any]:
    p = repo.find_by_id_card(id_card)
    if not p:
        raise HTTPException(status_code=404, detail='not found')
    return _mask_patient(p)


@router.get('/search/duplicates')
def find_duplicates(
    repo: PatientRepository = Depends(get_repo),
) -> Dict[str, Any]:
    groups = repo.find_duplicates_by_id_card()
    return {'duplicate_groups': groups, 'count': len(groups)}


@router.get('/{patient_id}/birth_year')
def compute_birth_year(
    patient_id: str,
    repo: PatientRepository = Depends(get_repo),
) -> Dict[str, Any]:
    year = repo.calculate_birth_year_from_id_card(patient_id)
    if year is None:
        raise HTTPException(status_code=404, detail='no id_card or invalid format')
    return {'patient_id': patient_id, 'birth_year': year}
