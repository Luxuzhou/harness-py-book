"""
临床路径分析路由。

路径分析是一种长耗时任务，典型做法是：
POST  /pathways/tasks                提交一个分析任务（异步）
GET   /pathways/tasks                列出任务
GET   /pathways/tasks/{task_id}      任务详情
POST  /pathways/tasks/{task_id}/cancel

分析结果：
GET   /pathways/results/{task_id}    返回分析产物（依从率、偏差、异常归因）

为避免在 FastAPI 同步处理长任务，路由只做"任务注册 + 结果查询"，
真实计算由 pathway_analyzer 完成（这里以内存任务存储做演示）。
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


@dataclass
class PathwayTask:
    """内存态的分析任务。"""
    task_id: str
    task_name: str
    step_code: str
    instrument_id: Optional[str]
    filters: Dict[str, Any]
    created_at: str
    status: str = 'PENDING'  # PENDING / RUNNING / SUCCEEDED / FAILED / CANCELLED
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    progress: int = 0
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class _TaskRegistry:
    """内存态任务注册表（进程内单例）。"""
    def __init__(self):
        self._tasks: Dict[str, PathwayTask] = {}
        self._lock = threading.RLock()
        self._background_threads: Dict[str, threading.Thread] = {}

    def create(self, task: PathwayTask) -> None:
        with self._lock:
            self._tasks[task.task_id] = task

    def get(self, task_id: str) -> Optional[PathwayTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, status_filter: Optional[str] = None) -> List[PathwayTask]:
        with self._lock:
            items = list(self._tasks.values())
        if status_filter:
            items = [t for t in items if t.status == status_filter]
        return sorted(items, key=lambda t: t.created_at, reverse=True)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t or t.status in {'SUCCEEDED', 'FAILED', 'CANCELLED'}:
                return False
            t.status = 'CANCELLED'
            t.finished_at = datetime.now().isoformat()
            return True

    def attach_thread(self, task_id: str, th: threading.Thread) -> None:
        self._background_threads[task_id] = th


_registry: Optional[_TaskRegistry] = None


def get_registry() -> _TaskRegistry:
    global _registry
    if _registry is None:
        _registry = _TaskRegistry()
    return _registry


def _reset_repo_for_tests() -> None:
    global _registry
    _registry = _TaskRegistry()


class PathwayAnalysisRequest(BaseModel):
    task_name: str
    step_code: str
    instrument_id: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    start_immediately: bool = True


class PathwayTaskResponse(BaseModel):
    task_id: str
    task_name: str
    step_code: str
    status: str
    progress: int
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None


def _run_pathway_analysis(task: PathwayTask, registry: _TaskRegistry) -> None:
    """
    在后台线程执行分析。当前版本走演示逻辑；生产场景调用 pathway_analyzer。
    """
    logger.info('pathway analysis start: %s', task.task_id)
    task.status = 'RUNNING'
    task.started_at = datetime.now().isoformat()
    try:
        # 模拟分步进度
        for step in range(1, 11):
            time.sleep(0.01)  # 演示用：真实场景是批量统计与 outlier 检测
            task.progress = step * 10
            if task.status == 'CANCELLED':
                logger.info('pathway analysis cancelled: %s', task.task_id)
                return

        # 计算分析结果（这里拼出一个演示结构）
        result = {
            'step_code': task.step_code,
            'instrument_id': task.instrument_id,
            'compliance_rate': 0.92,
            'deviation_points': [],
            'anomaly_causes': [
                {'code': 'INSTRUMENT_DRIFT', 'count': 3},
                {'code': 'SPECIMEN_QUALITY', 'count': 1},
            ],
            'filters_applied': task.filters,
        }
        task.result = result
        task.status = 'SUCCEEDED'
    except Exception as e:
        task.status = 'FAILED'
        task.error = f'{type(e).__name__}: {e}'
        logger.warning('pathway analysis failed %s: %s', task.task_id, e)
    finally:
        task.finished_at = datetime.now().isoformat()


@router.post('/tasks', response_model=PathwayTaskResponse)
def submit_task(
    payload: PathwayAnalysisRequest,
    registry: _TaskRegistry = Depends(get_registry),
) -> PathwayTaskResponse:
    task = PathwayTask(
        task_id=f'PT-{uuid.uuid4().hex[:12]}',
        task_name=payload.task_name,
        step_code=payload.step_code,
        instrument_id=payload.instrument_id,
        filters=dict(payload.filters),
        created_at=datetime.now().isoformat(),
    )
    registry.create(task)
    if payload.start_immediately:
        th = threading.Thread(
            target=_run_pathway_analysis, args=(task, registry), daemon=True,
        )
        th.start()
        registry.attach_thread(task.task_id, th)
    return PathwayTaskResponse(
        task_id=task.task_id, task_name=task.task_name,
        step_code=task.step_code, status=task.status,
        progress=task.progress, created_at=task.created_at,
    )


@router.get('/tasks')
def list_tasks(
    status: Optional[str] = None,
    registry: _TaskRegistry = Depends(get_registry),
) -> Dict[str, Any]:
    items = registry.list_tasks(status_filter=status)
    return {
        'count': len(items),
        'tasks': [
            {
                'task_id': t.task_id,
                'task_name': t.task_name,
                'step_code': t.step_code,
                'status': t.status,
                'progress': t.progress,
                'created_at': t.created_at,
                'started_at': t.started_at,
                'finished_at': t.finished_at,
            }
            for t in items
        ],
    }


@router.get('/tasks/{task_id}', response_model=PathwayTaskResponse)
def get_task(
    task_id: str,
    registry: _TaskRegistry = Depends(get_registry),
) -> PathwayTaskResponse:
    t = registry.get(task_id)
    if not t:
        raise HTTPException(status_code=404, detail='task not found')
    return PathwayTaskResponse(
        task_id=t.task_id, task_name=t.task_name,
        step_code=t.step_code, status=t.status,
        progress=t.progress, created_at=t.created_at,
        started_at=t.started_at, finished_at=t.finished_at,
        error=t.error,
    )


@router.post('/tasks/{task_id}/cancel')
def cancel_task(
    task_id: str,
    registry: _TaskRegistry = Depends(get_registry),
) -> Dict[str, Any]:
    ok = registry.cancel(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail='cannot cancel task')
    return {'task_id': task_id, 'status': 'CANCELLED'}


@router.get('/results/{task_id}')
def get_result(
    task_id: str,
    registry: _TaskRegistry = Depends(get_registry),
) -> Dict[str, Any]:
    t = registry.get(task_id)
    if not t:
        raise HTTPException(status_code=404, detail='task not found')
    if t.status != 'SUCCEEDED':
        raise HTTPException(
            status_code=409,
            detail=f'task not succeeded yet (status={t.status})')
    return {
        'task_id': task_id,
        'status': t.status,
        'result': t.result,
    }


@router.get('/results/{task_id}/summary')
def get_summary(
    task_id: str,
    registry: _TaskRegistry = Depends(get_registry),
) -> Dict[str, Any]:
    t = registry.get(task_id)
    if not t:
        raise HTTPException(status_code=404, detail='task not found')
    if not t.result:
        return {'task_id': task_id, 'summary': None, 'status': t.status}
    r = t.result
    return {
        'task_id': task_id,
        'status': t.status,
        'step_code': r.get('step_code'),
        'compliance_rate': r.get('compliance_rate'),
        'total_anomaly_causes': len(r.get('anomaly_causes') or []),
    }
