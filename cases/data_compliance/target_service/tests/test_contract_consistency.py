"""
契约一致性测试：验证 Python Pydantic 模型与 OpenAPI 契约的字段一致性。
"""

import pytest
from pydantic import BaseModel

from app.models.schemas import (
    AnomalyRuleResponse,
    AnomalyEventCreateRequest,
    AnomalyEventResponse,
    DeviationPoint,
    ErrorResponse,
)


class TestAnomalyRuleResponse:
    def test_has_all_required_fields(self):
        fields = set(AnomalyRuleResponse.model_fields.keys())
        expected = {
            "id", "test_item_id", "test_item_name", "window_size",
            "consecutive_count", "threshold_multiplier", "target_value",
            "sd_value", "enabled", "created_at", "updated_at",
        }
        assert expected.issubset(fields), f"缺失字段: {expected - fields}"

    def test_field_types(self):
        fields = AnomalyRuleResponse.model_fields
        assert fields["id"].annotation == int
        assert fields["test_item_id"].annotation == str
        assert fields["window_size"].annotation == int
        assert fields["enabled"].annotation == bool

    def test_model_config(self):
        assert hasattr(AnomalyRuleResponse, "model_config")


class TestAnomalyEventCreateRequest:
    def test_has_all_required_fields(self):
        fields = set(AnomalyEventCreateRequest.model_fields.keys())
        expected = {
            "rule_id", "test_item_id", "triggered_at", "severity",
            "moving_averages", "deviation_points", "message",
        }
        assert expected.issubset(fields), f"缺失字段: {expected - fields}"

    def test_severity_maxlength(self):
        fields = AnomalyEventCreateRequest.model_fields
        # Pydantic V2 使用 metadata 存储约束
        from pydantic import Field
        test_item_meta = fields["test_item_id"].metadata
        message_meta = fields["message"].metadata
        assert any(getattr(m, "max_length", None) == 64 for m in test_item_meta)
        assert any(getattr(m, "max_length", None) == 512 for m in message_meta)


class TestAnomalyEventResponse:
    def test_has_all_required_fields(self):
        fields = set(AnomalyEventResponse.model_fields.keys())
        expected = {
            "id", "rule_id", "test_item_id", "triggered_at",
            "severity", "message", "created_at",
        }
        assert expected.issubset(fields), f"缺失字段: {expected - fields}"


class TestDeviationPoint:
    def test_has_all_required_fields(self):
        fields = set(DeviationPoint.model_fields.keys())
        expected = {
            "index", "moving_average", "upper_limit",
            "lower_limit", "direction",
        }
        assert expected.issubset(fields), f"缺失字段: {expected - fields}"

    def test_direction_type_is_str(self):
        fields = DeviationPoint.model_fields
        assert fields["direction"].annotation == str


class TestErrorResponse:
    def test_has_all_required_fields(self):
        fields = set(ErrorResponse.model_fields.keys())
        expected = {"error_code", "message", "timestamp"}
        assert expected.issubset(fields), f"缺失字段: {expected - fields}"


class TestSchemaCount:
    def test_all_schemas_present(self):
        """验证关键 schema 均已定义。"""
        schemas = [
            AnomalyRuleResponse,
            AnomalyEventCreateRequest,
            AnomalyEventResponse,
            DeviationPoint,
            ErrorResponse,
        ]
        for s in schemas:
            assert issubclass(s, BaseModel), f"{s.__name__} 不是 BaseModel 子类"
