"""
按业务域拆分的 REST 路由模块。

每个模块聚焦一个清晰的业务域：
- patients.py     患者管理
- lab_results.py  检验结果查询
- instruments.py  仪器管理
- pathways.py     临床路径分析
- anomalies.py    异常规则与告警
- exports.py      数据导出
- admin.py        系统管理

原有 `app/api/endpoints.py` 作为向下兼容入口保留，内部委托到以下子路由。
"""

from fastapi import APIRouter

from app.api.routes.patients import router as patients_router
from app.api.routes.lab_results import router as lab_results_router
from app.api.routes.instruments import router as instruments_router
from app.api.routes.pathways import router as pathways_router
from app.api.routes.anomalies import router as anomalies_router
from app.api.routes.exports import router as exports_router
from app.api.routes.admin import router as admin_router


def register_routes(app_router: APIRouter) -> None:
    """把所有子路由挂载到传入的 APIRouter 上。"""
    app_router.include_router(patients_router, prefix='/patients', tags=['patients'])
    app_router.include_router(lab_results_router, prefix='/lab_results', tags=['lab_results'])
    app_router.include_router(instruments_router, prefix='/instruments', tags=['instruments'])
    app_router.include_router(pathways_router, prefix='/pathways', tags=['pathways'])
    app_router.include_router(anomalies_router, prefix='/anomalies', tags=['anomalies'])
    app_router.include_router(exports_router, prefix='/exports', tags=['exports'])
    app_router.include_router(admin_router, prefix='/admin', tags=['admin'])


__all__ = ['register_routes']
