"""
审计日志中间件
坏味道: 审计日志形同虚设——仅存在内存中，不持久化，不记录关键操作
"""

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# 坏味道: 内存存储，重启后丢失
_audit_log: List[Dict[str, Any]] = []
MAX_LOG_SIZE = 10000


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    审计日志中间件

    坏味道:
    1. 仅记录HTTP级别信息，不记录具体的数据访问操作
    2. 不记录谁做了什么（缺少用户身份信息）
    3. 不记录访问了哪些患者数据
    4. 不记录导出操作的数据范围
    5. 日志仅存在内存中
    """

    async def dispatch(self, request: Request,
                       call_next: Callable) -> Response:
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time

        # 记录基础请求信息（坏味道: 不够详细）
        entry = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_seconds": round(duration, 4),
            "client_ip": request.client.host if request.client else "unknown",
            # 坏味道: 不记录用户身份
            "user": "unknown",
        }

        _audit_log.append(entry)

        # 坏味道: 超过上限直接截断，不备份
        if len(_audit_log) > MAX_LOG_SIZE:
            _audit_log.pop(0)

        return response


def get_audit_log(limit: int = 100) -> List[Dict[str, Any]]:
    """获取审计日志"""
    return _audit_log[-limit:]


def get_audit_summary() -> Dict[str, Any]:
    """获取审计摘要"""
    if not _audit_log:
        return {"total_entries": 0}

    methods = {}
    paths = {}
    for entry in _audit_log:
        m = entry.get("method", "")
        p = entry.get("path", "")
        methods[m] = methods.get(m, 0) + 1
        paths[p] = paths.get(p, 0) + 1

    return {
        "total_entries": len(_audit_log),
        "by_method": methods,
        "top_paths": dict(
            sorted(paths.items(), key=lambda x: x[1], reverse=True)[:10]
        ),
    }
