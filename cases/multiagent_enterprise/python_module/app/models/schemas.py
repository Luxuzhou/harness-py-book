"""Pydantic 数据模型 -- 与 api_contract.yaml 对齐。

骨架代码 -- Agent 需要补充：
- 所有字段的类型注解和 Field 约束
- 与 OpenAPI 契约中 schema 的字段一一对应
- 枚举类型（Severity, DeviationDirection）
- 分析专用模型（AnomalyResult, HistoryAnalysis）

字段命名统一使用 snake_case（与契约一致）。
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    """异常预警严重程度。"""
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class DeviationDirection(str, Enum):
    """超限方向。"""
    HIGH = "HIGH"
    LOW = "LOW"


class DeviationPoint(BaseModel):
    """超限点位信息。"""
    # TODO: Agent 补充字段
    # index: int
    # moving_average: float
    # upper_limit: float
    # lower_limit: float
    # direction: DeviationDirection
    pass


class AnomalyRuleResponse(BaseModel):
    """预警规则响应（对应 Java 端返回）。"""
    model_config = ConfigDict(from_attributes=True)
    # TODO: Agent 补充字段 -- 与 api_contract.yaml AnomalyRuleResponse 一致
    pass


class AnomalyEventCreateRequest(BaseModel):
    """异常事件创建请求（Python 端发往 Java 端）。"""
    # TODO: Agent 补充字段 -- 与 api_contract.yaml AnomalyEventCreateRequest 一致
    pass


class AnomalyEventResponse(BaseModel):
    """异常事件响应（Java 端返回）。"""
    model_config = ConfigDict(from_attributes=True)
    # TODO: Agent 补充字段 -- 与 api_contract.yaml AnomalyEventResponse 一致
    pass


class ErrorResponse(BaseModel):
    """错误响应（对应 Java 端统一错误格式）。"""
    # TODO: Agent 补充字段 -- 与 api_contract.yaml ErrorResponse 一致
    # error_code: str
    # message: str
    # timestamp: Optional[datetime]
    pass


# ----- 分析专用模型（非契约模型，Python端内部使用） -----

class AnomalyResult(BaseModel):
    """实时分析结果。"""
    # TODO: Agent 补充字段
    # triggered: bool
    # moving_averages: list[float]
    # deviation_points: list[DeviationPoint]
    # message: Optional[str]
    pass


class HistoryAnalysis(BaseModel):
    """历史分析结果。"""
    # TODO: Agent 补充字段
    # moving_averages: list[float]
    # deviation_points: list[DeviationPoint]
    # anomaly_segments: list[dict]   # 连续超限区段
    # summary: dict                # 统计摘要
    pass
