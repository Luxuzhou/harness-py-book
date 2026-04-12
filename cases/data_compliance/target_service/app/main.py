"""
FastAPI应用入口
医疗诊疗数据处理系统 - PathwayAnalytics Data Service
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.endpoints import router as api_router
from app.core.config import settings
from app.middleware.tracing import TracingMiddleware
from app.middleware.audit_log import AuditLogMiddleware

# 坏味道: 基础日志配置不够完善
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 应用启动时间
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("PathwayAnalytics Data Service启动中...")
    print("[DEBUG] Application starting...")
    yield
    logger.info("PathwayAnalytics Data Service关闭")
    print("[DEBUG] Application shutdown")


app = FastAPI(
    title="PathwayAnalytics Data Service",
    description="医疗诊疗数据处理系统 - 基于患者数据的实时临床路径分析",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS配置
# 坏味道: 允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 自定义中间件
app.add_middleware(TracingMiddleware)
app.add_middleware(AuditLogMiddleware)

# 路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """健康检查端点"""
    uptime = time.time() - _start_time
    return {
        "status": "ok",
        "version": "1.0.0",
        "uptime_seconds": round(uptime, 2),
        "environment": settings.ENVIRONMENT,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    # 坏味道: 在生产环境暴露详细错误信息
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    print(f"[ERROR] Unhandled: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": f"Internal server error: {str(exc)}",
            "code": 500,
        },
    )
