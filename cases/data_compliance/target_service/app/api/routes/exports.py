"""
数据导出路由。

POST /exports/patients     导出患者（自动脱敏）
POST /exports/lab_results  导出检验结果
POST /exports/instruments  导出仪器清单
POST /exports/anomalies    导出异常清单
GET  /exports/history      导出历史
GET  /exports/download/{name}  下载生成的导出文件
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.routes.anomalies import get_anomaly_repo
from app.api.routes.instruments import get_repo as get_instrument_repo
from app.api.routes.lab_results import get_repo as get_lab_repo
from app.api.routes.patients import get_repo as get_patient_repo
from app.services.export.exporter_factory import (
    ExporterFactory, ExportPolicy, ExportValidationError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


_factory: Optional[ExporterFactory] = None
_history: List[Dict[str, Any]] = []


def get_factory() -> ExporterFactory:
    global _factory
    if _factory is None:
        target = Path(__file__).resolve().parents[3]
        out_dir = target / 'exports'
        policy = ExportPolicy(
            allowed_output_dirs=[out_dir],
        )
        _factory = ExporterFactory(default_output_dir=out_dir, policy=policy)
    return _factory


def _reset_repo_for_tests() -> None:
    global _factory, _history
    _factory = None
    _history = []


class ExportRequest(BaseModel):
    format: str = Field(default='csv')  # csv / xlsx / pdf
    fields: List[str] = Field(default_factory=list)
    max_rows: Optional[int] = None
    apply_mask: bool = True
    filters: Dict[str, Any] = Field(default_factory=dict)


def _record_history(entry: Dict[str, Any]) -> None:
    _history.append(entry)
    if len(_history) > 500:
        del _history[:-500]


@router.post('/patients')
def export_patients(
    payload: ExportRequest,
    factory: ExporterFactory = Depends(get_factory),
) -> Dict[str, Any]:
    repo = get_patient_repo()
    fields = payload.fields or [
        'patient_id', 'name', 'id_card', 'gender',
        'age', 'department', 'diagnosis',
    ]
    try:
        factory.validate_request(payload.format, fields, payload.max_rows)
    except ExportValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    records = repo.list(filters=payload.filters or None)
    filename = factory.build_filename('patients', payload.format)
    out = _dispatch(factory, payload.format, records, fields, filename,
                     payload.apply_mask)
    _record_history({'domain': 'patients', **out})
    return out


@router.post('/lab_results')
def export_lab_results(
    payload: ExportRequest,
    factory: ExporterFactory = Depends(get_factory),
) -> Dict[str, Any]:
    repo = get_lab_repo()
    fields = payload.fields or [
        'result_id', 'patient_id', 'step_code', 'step_name',
        'value', 'unit', 'department_id', 'visit_date', 'flag',
    ]
    try:
        factory.validate_request(payload.format, fields, payload.max_rows)
    except ExportValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    records = repo.list(filters=payload.filters or None)
    filename = factory.build_filename('lab_results', payload.format)
    out = _dispatch(factory, payload.format, records, fields, filename,
                     payload.apply_mask)
    _record_history({'domain': 'lab_results', **out})
    return out


@router.post('/instruments')
def export_instruments(
    payload: ExportRequest,
    factory: ExporterFactory = Depends(get_factory),
) -> Dict[str, Any]:
    repo = get_instrument_repo()
    fields = payload.fields or [
        'department_id', 'name', 'manufacturer', 'model',
        'serial_number', 'department', 'location', 'status',
        'last_calibration', 'next_calibration', 'daily_capacity',
    ]
    try:
        factory.validate_request(payload.format, fields, payload.max_rows)
    except ExportValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    records = repo.list(filters=payload.filters or None)
    filename = factory.build_filename('instruments', payload.format)
    out = _dispatch(factory, payload.format, records, fields, filename,
                     payload.apply_mask)
    _record_history({'domain': 'instruments', **out})
    return out


@router.post('/anomalies')
def export_anomalies(
    payload: ExportRequest,
    factory: ExporterFactory = Depends(get_factory),
) -> Dict[str, Any]:
    repo = get_anomaly_repo()
    fields = payload.fields or [
        'anomaly_id', 'rule_id', 'severity', 'status',
        'target_type', 'target_id', 'description',
        'detected_at', 'resolved_at', 'handler',
    ]
    try:
        factory.validate_request(payload.format, fields, payload.max_rows)
    except ExportValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    records = repo.list(filters=payload.filters or None)
    filename = factory.build_filename('anomalies', payload.format)
    out = _dispatch(factory, payload.format, records, fields, filename,
                     payload.apply_mask)
    _record_history({'domain': 'anomalies', **out})
    return out


@router.get('/history')
def list_history(
    limit: int = Query(default=50, ge=1, le=500),
) -> Dict[str, Any]:
    return {'count': len(_history), 'data': _history[-limit:]}


@router.get('/download/{filename}')
def download(
    filename: str,
    factory: ExporterFactory = Depends(get_factory),
):
    # 基础安全：禁止路径穿越
    if '/' in filename or '\\' in filename or '..' in filename:
        raise HTTPException(status_code=400, detail='invalid filename')
    path = factory.default_output_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail='export file not found')
    return FileResponse(
        str(path),
        filename=filename,
        media_type='application/octet-stream',
    )


def _dispatch(
    factory: ExporterFactory,
    format: str,
    records: List[Dict[str, Any]],
    fields: List[str],
    filename: str,
    apply_mask: bool,
) -> Dict[str, Any]:
    """根据 format 分派到对应 exporter。"""
    if format == 'csv':
        exp = factory.csv()
        return exp.export(records, fields, filename, apply_mask=apply_mask)
    if format == 'xlsx':
        exp = factory.excel()
        return exp.export_single(records, fields, filename, apply_mask=apply_mask)
    if format == 'pdf':
        exp = factory.pdf()
        # PDF 不走 fields/records，需要 report_data；这里构造一个最小报表
        report_data = {
            'generated_at': filename,
            'period': 'export',
            'patient_overview': {'total': len(records)},
            'lab_result_summary': {'total_results': len(records)},
            'anomaly_summary': {},
            'instrument_summary': {},
            'audit_summary': {},
        }
        return exp.generate(report_data, filename)
    raise HTTPException(status_code=400, detail=f'unknown format: {format}')
