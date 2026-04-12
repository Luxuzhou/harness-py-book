"""
API端点定义
坏味道: 端点不验证调用者身份、数据返回未脱敏
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from app.models.schemas import (
    AnalysisResultResponse,
    BatchAnalysisResponse,
    BaseResponse,
    DataQualityResponse,
    ExportRequest,
    ExportResponse,
    HealthCheck,
    HealthCheckResponse,
    InstrumentComparisonRequest,
    InstrumentComparisonResponse,
    InstrumentListResponse,
    LabResultBatchCreate,
    LabResultListResponse,
    NormalizationRequest,
    NormalizationResponse,
    PatientListResponse,
    PatientResponse,
    QueryRequest,
    QueryResponse,
    TaskConfig,
    TaskConfigCreate,
    TaskConfigListResponse,
    TaskConfigResponse,
    TrendAnalysisRequest,
    TrendAnalysisResponse,
)
from app.services.data_processor import DataProcessor
from app.services.export_service import ExportService
from app.services.filter_service import FilterService
from app.services.normalization_service import NormalizationService
from app.services.pathway_analyzer import PathwayAnalyzer, AnalysisConfig
from app.services.query_service import QueryService

logger = logging.getLogger(__name__)

router = APIRouter()

# 服务实例（坏味道: 全局单例，无依赖注入）
_data_processor = DataProcessor()
_query_service = QueryService()
_filter_service = FilterService()
_export_service = ExportService()
_normalization_service = NormalizationService()
_analyzer = PathwayAnalyzer()

# 内存存储（模拟数据库）
_patients_store: List[Dict[str, Any]] = []
_results_store: List[Dict[str, Any]] = []
_departments_store: List[Dict[str, Any]] = []
_tasks_store: Dict[str, TaskConfig] = {}


# ──────────────────────────────────────────────────────────────
# 患者端点
# ──────────────────────────────────────────────────────────────
@router.get("/patients", response_model=PatientListResponse)
async def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    department: Optional[str] = None,
    gender: Optional[str] = None,
):
    """
    获取患者列表
    坏味道: 不验证身份、返回未脱敏PII
    """
    # 坏味道: 不检查调用者权限
    filtered = _patients_store

    if department:
        filtered = [p for p in filtered if p.get("department") == department]
    if gender:
        filtered = [p for p in filtered if p.get("gender") == gender]

    start = (page - 1) * page_size
    end = start + page_size
    page_data = filtered[start:end]

    # 坏味道: 直接返回包含PII的数据
    print(f"[DEBUG] Listing patients: page={page}, total={len(filtered)}")
    logger.info(f"查询患者列表: 返回{len(page_data)}条")

    return PatientListResponse(
        data=page_data,
        pagination={"page": page, "page_size": page_size,
                    "total": len(filtered)},
    )


@router.get("/patients/{patient_id}")
async def get_patient(patient_id: str):
    """
    获取单个患者信息
    坏味道: 返回完整PII（姓名、身份证号）
    """
    for p in _patients_store:
        if p.get("patient_id") == patient_id:
            # 坏味道: 日志中明文记录patient_id
            print(f"[DEBUG] Patient found: {patient_id}")
            logger.info(f"查询患者: patient_id={patient_id}")
            return {"success": True, "data": p}

    raise HTTPException(status_code=404, detail=f"患者不存在: {patient_id}")


# ──────────────────────────────────────────────────────────────
# 诊疗记录端点
# ──────────────────────────────────────────────────────────────
@router.get("/lab-results", response_model=LabResultListResponse)
async def list_treatment_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    step_code: Optional[str] = None,
    department_id: Optional[str] = None,
    patient_id: Optional[str] = None,
):
    """获取诊疗记录列表"""
    filtered = _results_store

    if step_code:
        filtered = [r for r in filtered if r.get("step_code") == step_code]
    if department_id:
        filtered = [r for r in filtered
                    if r.get("department_id") == department_id]
    if patient_id:
        filtered = [r for r in filtered
                    if r.get("patient_id") == patient_id]
        # 坏味道: 日志暴露patient_id
        logger.info(f"按patient_id过滤: {patient_id}")

    start = (page - 1) * page_size
    end = start + page_size

    return LabResultListResponse(
        data=filtered[start:end],
        pagination={"page": page, "page_size": page_size,
                    "total": len(filtered)},
    )


@router.post("/lab-results/batch")
async def batch_create_results(batch: LabResultBatchCreate):
    """批量创建诊疗记录"""
    created = 0
    for result in batch.results:
        record = result.model_dump()
        record["created_at"] = datetime.now().isoformat()
        _results_store.append(record)
        created += 1

    print(f"[DEBUG] Batch created {created} results")
    return BaseResponse(
        message=f"成功创建{created}条诊疗记录",
    )


# ──────────────────────────────────────────────────────────────
# 科室端点
# ──────────────────────────────────────────────────────────────
@router.get("/departments", response_model=InstrumentListResponse)
async def list_departments():
    """获取科室列表"""
    return InstrumentListResponse(data=_departments_store)


@router.get("/departments/{department_id}")
async def get_department(department_id: str):
    """获取科室详情"""
    for inst in _departments_store:
        if inst.get("department_id") == department_id:
            return {"success": True, "data": inst}
    raise HTTPException(status_code=404,
                        detail=f"科室不存在: {department_id}")


# ──────────────────────────────────────────────────────────────
# 查询端点
# ──────────────────────────────────────────────────────────────
@router.post("/query", response_model=QueryResponse)
async def query_data(request: QueryRequest):
    """
    执行数据查询
    坏味道: SQL字符串拼接
    """
    start_time = datetime.now()

    result = _query_service.query_treatment_records(
        step_codes=request.step_codes,
        department_ids=request.department_ids,
        start_date=(request.time_range.start_date
                    if request.time_range else None),
        end_date=(request.time_range.end_date
                  if request.time_range else None),
    )

    elapsed = (datetime.now() - start_time).total_seconds() * 1000

    return QueryResponse(
        data=[result],
        query_time_ms=elapsed,
        total_count=1,
    )


# ──────────────────────────────────────────────────────────────
# 分析端点
# ──────────────────────────────────────────────────────────────
@router.post("/analysis/run")
async def run_analysis(config: TaskConfigCreate):
    """执行PathwayAnalytics分析"""
    analysis_config = AnalysisConfig(
        step_code=config.step_code,
        department_id=config.department_id or "",
        window_size=(config.ma_config.window_size
                     if config.ma_config else 20),
        ma_method=(config.ma_config.method.value
                   if config.ma_config else "EWMA"),
        min_data_points=config.min_data_points,
    )

    # 从内存存储获取数据
    relevant_results = [
        r for r in _results_store
        if r.get("step_code") == config.step_code
    ]

    if not relevant_results:
        return BaseResponse(
            success=False,
            message=f"无数据: step_code={config.step_code}",
            code=404,
        )

    result = _analyzer.run_full_analysis(relevant_results, analysis_config)

    return AnalysisResultResponse(
        data=result,
        message="分析完成",
    )


@router.post("/analysis/batch")
async def run_batch_analysis(
    step_codes: List[str],
    department_id: Optional[str] = None,
):
    """批量分析多个诊疗环节"""
    data_by_test: Dict[str, List[Dict[str, Any]]] = {}
    for tc in step_codes:
        data_by_test[tc] = [
            r for r in _results_store if r.get("step_code") == tc
        ]

    results = _analyzer.batch_analyze(data_by_test)

    completed = sum(1 for r in results.values()
                    if r.get("status") == "completed")
    failed = sum(1 for r in results.values()
                 if r.get("status") in ("error", "insufficient_data"))

    return BatchAnalysisResponse(
        data=results,
        total_tests=len(step_codes),
        completed=completed,
        failed=failed,
    )


@router.post("/analysis/trend")
async def analyze_trend(request: TrendAnalysisRequest):
    """趋势分析"""
    relevant = [
        r for r in _results_store
        if r.get("step_code") == request.step_code
    ]

    if len(relevant) < 10:
        return TrendAnalysisResponse(
            success=False,
            message="数据不足",
        )

    values = [float(r["value"]) for r in relevant
              if r.get("value") is not None]
    ma_result = _analyzer.compute_moving_average(
        values,
        method=request.ma_method.value,
        window=request.window_size,
    )

    trend = _analyzer.analyze_trend(ma_result.values)

    return TrendAnalysisResponse(data=trend)


@router.post("/analysis/quality")
async def data_quality(step_code: str):
    """数据质量评估"""
    relevant = [
        r for r in _results_store
        if r.get("step_code") == step_code
    ]

    values = [float(r["value"]) for r in relevant
              if r.get("value") is not None]

    if not values:
        return DataQualityResponse(
            success=False, message="无数据"
        )

    score = _analyzer.get_data_quality_score(values)
    return DataQualityResponse(data=score)


# ──────────────────────────────────────────────────────────────
# 导出端点
# ──────────────────────────────────────────────────────────────
@router.post("/export", response_model=ExportResponse)
async def export_data(request: ExportRequest):
    """
    导出数据
    坏味道: 不检查权限、不记录审计、默认包含PII
    """
    # 过滤数据
    filtered = _results_store
    if request.step_codes:
        filtered = [r for r in filtered
                    if r.get("step_code") in request.step_codes]
    if request.department_ids:
        filtered = [r for r in filtered
                    if r.get("department_id") in request.department_ids]

    # 限制行数
    filtered = filtered[:request.max_rows]

    # 如果需要患者信息，合并
    if request.include_patient_info:
        merged = _data_processor.merge_patient_results(
            _patients_store, filtered
        )
    else:
        merged = filtered

    # 导出
    format_val = request.format.value
    if format_val == "csv":
        result = _export_service.export_to_csv(
            merged,
            include_patient_info=request.include_patient_info,
        )
    elif format_val == "json":
        result = _export_service.export_to_json(
            merged,
            include_patient_info=request.include_patient_info,
        )
    elif format_val == "excel":
        result = _export_service.export_to_excel(
            merged,
            include_patient_info=request.include_patient_info,
        )
    else:
        result = _export_service.export_to_json(merged)

    return ExportResponse(
        download_url=result.get("filepath"),
        file_path=result.get("filepath"),
        file_size_bytes=result.get("file_size_bytes", 0),
        row_count=result.get("row_count", 0),
        format=format_val,
    )


# ──────────────────────────────────────────────────────────────
# 归一化端点
# ──────────────────────────────────────────────────────────────
@router.post("/normalization", response_model=NormalizationResponse)
async def normalize_data(request: NormalizationRequest):
    """科室间结果归一化"""
    source_data = [
        float(r["value"]) for r in _results_store
        if (r.get("step_code") == request.step_code and
            r.get("department_id") == request.source_department_id and
            r.get("value") is not None)
    ]
    ref_data = [
        float(r["value"]) for r in _results_store
        if (r.get("step_code") == request.step_code and
            r.get("department_id") == request.target_department_id and
            r.get("value") is not None)
    ]

    # 取较短的长度对齐
    min_len = min(len(source_data), len(ref_data))
    if min_len < request.min_pairs:
        return NormalizationResponse(
            success=False,
            message=f"配对数不足: {min_len} < {request.min_pairs}",
        )

    result = _normalization_service.normalize(
        source_data[:min_len],
        ref_data[:min_len],
        method=request.method.value,
    )

    return NormalizationResponse(data=result)


@router.post("/departments/compare",
             response_model=InstrumentComparisonResponse)
async def compare_departments(request: InstrumentComparisonRequest):
    """科室比较"""
    data1 = [
        float(r["value"]) for r in _results_store
        if (r.get("step_code") == request.step_code and
            r.get("department_id") == request.department_id_1 and
            r.get("value") is not None)
    ]
    data2 = [
        float(r["value"]) for r in _results_store
        if (r.get("step_code") == request.step_code and
            r.get("department_id") == request.department_id_2 and
            r.get("value") is not None)
    ]

    min_len = min(len(data1), len(data2))
    if min_len < 10:
        return InstrumentComparisonResponse(
            success=False, message="数据不足"
        )

    result = _normalization_service.compare_departments(
        data1[:min_len], data2[:min_len],
        step_code=request.step_code,
        method=request.regression_method.value,
    )

    return InstrumentComparisonResponse(data=result)


# ──────────────────────────────────────────────────────────────
# 任务管理端点
# ──────────────────────────────────────────────────────────────
@router.post("/tasks", response_model=TaskConfigResponse)
async def create_task(config: TaskConfigCreate):
    """创建分析任务"""
    import uuid
    task_id = str(uuid.uuid4())
    task = TaskConfig(
        task_id=task_id,
        step_code=config.step_code,
        step_name=config.step_name,
        department_id=config.department_id,
        min_data_points=config.min_data_points,
        created_at=datetime.now(),
    )
    if config.filters:
        task.filters = config.filters
    if config.qc_rules:
        task.qc_rules = config.qc_rules
    if config.ma_config:
        task.ma_config = config.ma_config

    _tasks_store[task_id] = task
    return TaskConfigResponse(data=task, message=f"任务已创建: {task_id}")


@router.get("/tasks", response_model=TaskConfigListResponse)
async def list_tasks():
    """获取任务列表"""
    return TaskConfigListResponse(data=list(_tasks_store.values()))


@router.get("/tasks/{task_id}", response_model=TaskConfigResponse)
async def get_task(task_id: str):
    """获取任务详情"""
    task = _tasks_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404,
                            detail=f"任务不存在: {task_id}")
    return TaskConfigResponse(data=task)


# ──────────────────────────────────────────────────────────────
# 数据加载端点
# ──────────────────────────────────────────────────────────────
@router.post("/data/load")
async def load_sample_data(data_dir: str = "sample_data"):
    """
    加载示例数据
    坏味道: 路径未验证
    """
    global _patients_store, _results_store, _departments_store

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_path = os.path.join(base_dir, data_dir)

    patients_path = os.path.join(data_path, "patients.csv")
    results_path = os.path.join(data_path, "treatment_records.csv")
    departments_path = os.path.join(data_path, "departments.csv")

    _patients_store = _data_processor.load_patients_csv(patients_path)
    _results_store = _data_processor.load_treatment_records_csv(results_path)
    _departments_store = _data_processor.load_departments_csv(departments_path)

    return BaseResponse(
        message=(f"数据加载完成: {len(_patients_store)}名患者, "
                f"{len(_results_store)}条结果, "
                f"{len(_departments_store)}台科室"),
    )


@router.get("/data/summary")
async def data_summary():
    """获取数据概况"""
    return {
        "success": True,
        "data": {
            "patients": len(_patients_store),
            "treatment_records": len(_results_store),
            "departments": len(_departments_store),
            "tasks": len(_tasks_store),
        },
    }


# ──────────────────────────────────────────────────────────────
# 过滤预设端点
# ──────────────────────────────────────────────────────────────
@router.get("/filters/presets")
async def list_filter_presets():
    """获取过滤预设列表"""
    return {
        "success": True,
        "data": _filter_service.list_presets(),
    }


@router.get("/filters/presets/{name}")
async def get_filter_preset(name: str):
    """获取过滤预设"""
    preset = _filter_service.get_preset(name)
    if not preset:
        raise HTTPException(status_code=404,
                            detail=f"预设不存在: {name}")
    return {
        "success": True,
        "data": preset.model_dump(),
    }
