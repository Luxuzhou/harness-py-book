"""Pydantic 数据模型 -- 与 api_contract.yaml 对齐。

骨架代码 -- Agent 需要补充：
- 所有字段的类型注解和 Field 约束
- 与 OpenAPI 契约中 schema 的字段一一对应
- 枚举类型（Severity, BreachDirection）
- 分析专用模型（AlarmResult, HistoryAnalysis）

字段命名统一使用 snake_case（与契约一致）。
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    """报警严重程度。"""
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class BreachDirection(str, Enum):
    """超限方向。"""
    HIGH = "HIGH"
    LOW = "LOW"


class BreachPoint(BaseModel):
    """超限点位信息。"""
    # TODO: Agent 补充字段
    # index: int
    # moving_average: float
    # upper_limit: float
    # lower_limit: float
    # direction: BreachDirection
    pass


class AlarmRuleResponse(BaseModel):
    """报警规则响应（对应 Java 端返回）。"""
    model_config = ConfigDict(from_attributes=True)
    # TODO: Agent 补充字段 -- 与 api_contract.yaml AlarmRuleResponse 一致
    pass


class AlarmEventCreateRequest(BaseModel):
    """报警事件创建请求（Python 端发往 Java 端）。"""
    # TODO: Agent 补充字段 -- 与 api_contract.yaml AlarmEventCreateRequest 一致
    pass


class AlarmEventResponse(BaseModel):
    """报警事件响应（Java 端返回）。"""
    model_config = ConfigDict(from_attributes=True)
    # TODO: Agent 补充字段 -- 与 api_contract.yaml AlarmEventResponse 一致
    pass


class ErrorResponse(BaseModel):
    """错误响应（对应 Java 端统一错误格式）。"""
    # TODO: Agent 补充字段 -- 与 api_contract.yaml ErrorResponse 一致
    # error_code: str
    # message: str
    # timestamp: Optional[datetime]
    pass


# ----- 分析专用模型（非契约模型，Python端内部使用） -----

class AlarmResult(BaseModel):
    """实时分析结果。"""
    # TODO: Agent 补充字段
    # triggered: bool
    # moving_averages: list[float]
    # breach_points: list[BreachPoint]
    # message: Optional[str]
    pass


class HistoryAnalysis(BaseModel):
    """历史分析结果。"""
    # TODO: Agent 补充字段
    # moving_averages: list[float]
    # breach_points: list[BreachPoint]
    # alarm_segments: list[dict]   # 连续超限区段
    # summary: dict                # 统计摘要
    pass
