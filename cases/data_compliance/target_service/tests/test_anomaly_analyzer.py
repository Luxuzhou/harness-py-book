"""
异常预警分析服务单元测试。
覆盖核心算法函数：compute_moving_averages、detect_deviationes、
以及连续超限判定逻辑。
"""

import pytest
import numpy as np

from app.services.anomaly_analyzer import (
    compute_moving_averages,
    detect_deviationes,
    _find_consecutive_segments,
    _determine_severity,
)
from app.models.schemas import DeviationPoint


# ──────────────────────────────────────────────────────────────
# compute_moving_averages
# ──────────────────────────────────────────────────────────────

class TestComputeMovingAverages:
    def test_basic_sequence(self):
        """输入 [1, 2, 3, 4, 5]，窗口=3，期望 [1.0, 1.5, 2.0, 3.0, 4.0]"""
        result = compute_moving_averages([1, 2, 3, 4, 5], 3)
        assert result == pytest.approx([1.0, 1.5, 2.0, 3.0, 4.0])

    def test_window_equals_length(self):
        """窗口大小等于序列长度"""
        result = compute_moving_averages([1, 2, 3], 3)
        assert result == pytest.approx([1.0, 1.5, 2.0])

    def test_single_value(self):
        """单个值的情况"""
        result = compute_moving_averages([5.0], 3)
        assert result == pytest.approx([5.0])

    def test_window_larger_than_sequence(self):
        """窗口大于序列长度，前几个用累积均值"""
        result = compute_moving_averages([1, 2], 5)
        assert result == pytest.approx([1.0, 1.5])

    def test_empty_input_raises(self):
        """空输入应抛出 ValueError"""
        with pytest.raises(ValueError, match="must not be empty"):
            compute_moving_averages([], 3)

    def test_invalid_window_raises(self):
        """无效窗口大小应抛出 ValueError"""
        with pytest.raises(ValueError, match="must be >= 1"):
            compute_moving_averages([1, 2, 3], 0)

    def test_golden_normal_sequence(self):
        """正常波动序列"""
        data = [5.4, 5.6, 5.5, 5.3, 5.7, 5.5, 5.4, 5.6]
        result = compute_moving_averages(data, 3)
        assert len(result) == len(data)
        assert all(5.0 < r < 6.0 for r in result)


# ──────────────────────────────────────────────────────────────
# detect_deviationes
# ──────────────────────────────────────────────────────────────

class TestDetectDeviations:
    def test_no_deviation(self):
        """所有值在控制限内"""
        mas = [5.4, 5.5, 5.6, 5.5, 5.4]
        points = detect_deviationes(mas, target=5.5, sd=0.3, threshold_multiplier=3.0)
        assert len(points) == 0

    def test_high_deviation(self):
        """值超过上控制限"""
        mas = [5.5, 5.5, 6.5]  # upper_limit = 5.5 + 1.5*0.3 = 5.95
        points = detect_deviationes(mas, target=5.5, sd=0.3, threshold_multiplier=1.5)
        assert len(points) == 1
        assert points[0].index == 2
        assert points[0].direction == "HIGH"

    def test_low_deviation(self):
        """值低于下控制限"""
        mas = [5.5, 5.5, 4.0]  # lower_limit = 5.5 - 1.5*0.3 = 5.05
        points = detect_deviationes(mas, target=5.5, sd=0.3, threshold_multiplier=1.5)
        assert len(points) == 1
        assert points[0].index == 2
        assert points[0].direction == "LOW"

    def test_multiple_deviations(self):
        """多个超限点"""
        mas = [4.0, 5.5, 6.5, 5.5, 4.0]
        points = detect_deviationes(mas, target=5.5, sd=0.3, threshold_multiplier=1.5)
        assert len(points) == 3
        assert points[0].index == 0
        assert points[1].index == 2
        assert points[2].index == 4

    def test_empty_input(self):
        """空输入返回空列表"""
        points = detect_deviationes([], target=5.5, sd=0.3, threshold_multiplier=1.5)
        assert points == []

    def test_boundary_exact_at_limit(self):
        """恰好等于控制限，不超限"""
        upper = 5.5 + 1.5 * 0.3  # 5.95
        mas = [5.5, upper, 5.5]
        points = detect_deviationes(mas, target=5.5, sd=0.3, threshold_multiplier=1.5)
        assert len(points) == 0


# ──────────────────────────────────────────────────────────────
# 连续超限判定逻辑
# ──────────────────────────────────────────────────────────────

class TestConsecutiveSegments:
    def test_consecutive_3_out_of_5(self):
        """连续 3 次超限，应识别区段"""
        points = [
            DeviationPoint(index=0, moving_average=6.0, upper_limit=6.0, lower_limit=5.0, direction="HIGH"),
            DeviationPoint(index=1, moving_average=6.1, upper_limit=6.0, lower_limit=5.0, direction="HIGH"),
            DeviationPoint(index=2, moving_average=6.2, upper_limit=6.0, lower_limit=5.0, direction="HIGH"),
        ]
        segments = _find_consecutive_segments(points, consecutive_count=3)
        assert len(segments) == 1
        assert len(segments[0]) == 3

    def test_insufficient_consecutive(self):
        """超限次数不足 N 次，不应触发"""
        points = [
            DeviationPoint(index=0, moving_average=6.0, upper_limit=6.0, lower_limit=5.0, direction="HIGH"),
            DeviationPoint(index=2, moving_average=6.1, upper_limit=6.0, lower_limit=5.0, direction="HIGH"),
        ]
        segments = _find_consecutive_segments(points, consecutive_count=3)
        assert len(segments) == 0

    def test_non_consecutive(self):
        """超限次数够但不连续，不应触发"""
        points = [
            DeviationPoint(index=0, moving_average=6.0, upper_limit=6.0, lower_limit=5.0, direction="HIGH"),
            DeviationPoint(index=1, moving_average=6.1, upper_limit=6.0, lower_limit=5.0, direction="HIGH"),
            DeviationPoint(index=3, moving_average=6.2, upper_limit=6.0, lower_limit=5.0, direction="HIGH"),
        ]
        segments = _find_consecutive_segments(points, consecutive_count=3)
        assert len(segments) == 0

    def test_n_minus_1_boundary(self):
        """恰好 N-1 次连续超限，不触发"""
        points = [
            DeviationPoint(index=0, moving_average=6.0, upper_limit=6.0, lower_limit=5.0, direction="HIGH"),
            DeviationPoint(index=1, moving_average=6.1, upper_limit=6.0, lower_limit=5.0, direction="HIGH"),
        ]
        segments = _find_consecutive_segments(points, consecutive_count=3)
        assert len(segments) == 0


class TestDetermineSeverity:
    def test_warning(self):
        """少量超限点 -> WARNING"""
        points = [DeviationPoint(index=0, moving_average=6.0, upper_limit=6.0, lower_limit=5.0, direction="HIGH")]
        assert _determine_severity(points, consecutive_count=3) == "WARNING"

    def test_critical(self):
        """大量超限点 -> CRITICAL"""
        points = [
            DeviationPoint(index=i, moving_average=6.0, upper_limit=6.0, lower_limit=5.0, direction="HIGH")
            for i in range(10)
        ]
        assert _determine_severity(points, consecutive_count=3) == "CRITICAL"


# ──────────────────────────────────────────────────────────────
# Golden 测试用例（回归测试）
# ──────────────────────────────────────────────────────────────

class TestGoldenCases:
    def test_golden_normal_sequence(self):
        """正常波动序列，不异常预警"""
        data = [5.4, 5.6, 5.5, 5.3, 5.7, 5.5, 5.4, 5.6]
        mas = compute_moving_averages(data, 3)
        points = detect_deviationes(mas, target=5.5, sd=0.3, threshold_multiplier=3.0)
        assert len(points) == 0

    def test_golden_gradual_drift(self):
        """渐变漂移序列，应异常预警"""
        data = [5.5, 5.6, 5.7, 5.8, 5.9, 6.0, 6.1, 6.2]
        mas = compute_moving_averages(data, 3)
        points = detect_deviationes(mas, target=5.5, sd=0.3, threshold_multiplier=1.5)
        assert len(points) >= 2  # MA 平滑后至少最后 2 个点超限

    def test_golden_spike_and_recover(self):
        """突变后恢复，不异常预警（连续超限不足）"""
        data = [5.5, 5.5, 6.5, 5.5, 5.5, 5.5, 5.5]
        mas = compute_moving_averages(data, 3)
        points = detect_deviationes(mas, target=5.5, sd=0.3, threshold_multiplier=1.5)
        # 只有一个明显的突变点，MA 会被平滑
        assert len(points) < 3

    def test_golden_boundary_n_minus_1(self):
        """恰好 N-1 次连续超限，不异常预警"""
        data = [5.5, 6.5, 6.5, 4.0, 5.5, 5.5, 5.5]  # MA[3]=[5.5,6.0,6.16,5.5] → 2 连续点
        mas = compute_moving_averages(data, 3)
        points = detect_deviationes(mas, target=5.5, sd=0.3, threshold_multiplier=1.5)
        segments = _find_consecutive_segments(points, consecutive_count=3)
        assert len(segments) == 0
