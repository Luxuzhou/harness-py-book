"""智能报警分析 API 端点。

骨架代码 -- Agent 需要补充：
- POST /api/v1/analyze/realtime  -- 实时报警分析
- POST /api/v1/analyze/history   -- 历史报警分析

实现要求：
- 路由函数使用 async def
- 请求/响应使用 Pydantic 模型
- 业务逻辑委托给 services/alarm_analyzer.py
- 不在此文件中实现算法逻辑
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/analyze", tags=["alarm-analysis"])


# TODO: POST /realtime
# - 接收 RealtimeAnalysisRequest（test_item_id + measurements）
# - 调用 alarm_analyzer.analyze_realtime
# - 返回 AlarmResult


# TODO: POST /history
# - 接收 HistoryAnalysisRequest（test_item_id + start_date + end_date + custom_params）
# - 调用 alarm_analyzer.analyze_history
# - 返回 HistoryAnalysis
