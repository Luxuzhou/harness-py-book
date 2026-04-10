"""
链路追踪中间件
提供请求级别的trace_id和基础性能追踪
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """
    链路追踪中间件

    为每个请求分配trace_id，记录请求耗时
    """

    async def dispatch(self, request: Request,
                       call_next: Callable) -> Response:
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        start_time = time.time()

        # 添加trace header
        try:
            response = await call_next(request)
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"[{trace_id}] {request.method} {request.url.path} "
                f"FAILED ({duration:.3f}s): {e}"
            )
            raise

        duration = time.time() - start_time
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"

        # 日志
        log_msg = (
            f"[{trace_id}] {request.method} {request.url.path} "
            f"-> {response.status_code} ({duration:.3f}s)"
        )

        if duration > 5.0:
            logger.warning(f"SLOW REQUEST: {log_msg}")
            print(f"[WARN] Slow request: {log_msg}")
        elif response.status_code >= 400:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        # 坏味道: print调试
        print(f"[TRACE] {log_msg}")

        return response


class RequestMetrics:
    """
    请求指标收集器
    坏味道: 仅内存存储，重启丢失
    """

    def __init__(self):
        self._request_count = 0
        self._total_duration = 0.0
        self._status_counts = {}
        self._slow_requests = []

    def record(self, method: str, path: str,
               status_code: int, duration: float):
        """记录请求指标"""
        self._request_count += 1
        self._total_duration += duration

        key = str(status_code)
        self._status_counts[key] = self._status_counts.get(key, 0) + 1

        if duration > 5.0:
            self._slow_requests.append({
                "method": method,
                "path": path,
                "duration": duration,
                "status": status_code,
            })
            # 只保留最近100条
            if len(self._slow_requests) > 100:
                self._slow_requests = self._slow_requests[-100:]

    def get_summary(self):
        """获取指标摘要"""
        avg_duration = (
            self._total_duration / self._request_count
            if self._request_count > 0
            else 0
        )
        return {
            "total_requests": self._request_count,
            "avg_duration_seconds": round(avg_duration, 4),
            "status_distribution": self._status_counts,
            "slow_request_count": len(self._slow_requests),
        }
