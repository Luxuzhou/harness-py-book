"""
路径变异智能预警分析服务。

提供基于路径依从率（Moving Average）的智能异常预警判定算法：
- compute_moving_averages: 计算路径依从率序列
- detect_deviationes: 检测超限点位
- analyze_realtime: 实时分析（调用 Java 端获取规则，判定并上报异常）
- analyze_history: 历史分析（使用 mock 数据或自定义参数回测）

核心算法函数为纯函数，便于单元测试。
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.clients.java_api_client import (
    JavaApiClient,
    JavaApiClientNotFoundError,
)
from app.models.schemas import (
    AnomalyEventCreateRequest,
    AnomalyResult,
    AnomalySegment,
    DeviationPoint,
    HistoryAnalysis,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 核心算法（纯函数）
# ──────────────────────────────────────────────────────────────


def compute_moving_averages(
    measurements: List[float],
    window_size: int,
) -> List[float]:
    """计算路径依从率序列。

    对于 i < window_size - 1 的位置，使用 measurements[0:i+1] 的均值。
    对于 i >= window_size - 1 的位置，使用 measurements[i-window_size+1:i+1] 的均值。

    Args:
        measurements: 测量值序列（按时间顺序）
        window_size: 路径依从率窗口大小（3~20）

    Returns:
        路径依从率序列，长度与 measurements 相同

    Raises:
        ValueError: 输入为空或 window_size < 1
    """
    if not measurements:
        raise ValueError("measurements must not be empty")
    if window_size < 1:
        raise ValueError("window_size must be >= 1")

    arr = np.array(measurements, dtype=np.float64)
    n = len(arr)
    result = np.empty(n, dtype=np.float64)

    for i in range(n):
        start = max(0, i - window_size + 1)
        result[i] = np.mean(arr[start:i + 1])

    return result.tolist()


def detect_deviationes(
    moving_averages: List[float],
    target: float,
    sd: float,
    threshold_multiplier: float,
) -> List[DeviationPoint]:
    """检测超限点位。

    控制限计算：
        upper_limit = target + threshold_multiplier * sd
        lower_limit = target - threshold_multiplier * sd

    当 moving_average > upper_limit 时，方向为 HIGH；
    当 moving_average < lower_limit 时，方向为 LOW。

    Args:
        moving_averages: 路径依从率序列
        target: 目标值（靶值）
        sd: 标准差
        threshold_multiplier: 控制限倍数

    Returns:
        超限点位列表，按索引升序排列
    """
    if not moving_averages:
        return []

    upper_limit = target + threshold_multiplier * sd
    lower_limit = target - threshold_multiplier * sd

    points: List[DeviationPoint] = []
    for i, ma in enumerate(moving_averages):
        if ma > upper_limit:
            points.append(DeviationPoint(
                index=i,
                moving_average=ma,
                upper_limit=upper_limit,
                lower_limit=lower_limit,
                direction="HIGH",
            ))
        elif ma < lower_limit:
            points.append(DeviationPoint(
                index=i,
                moving_average=ma,
                upper_limit=upper_limit,
                lower_limit=lower_limit,
                direction="LOW",
            ))

    return points


def _find_consecutive_segments(
    deviation_points: List[DeviationPoint],
    consecutive_count: int,
) -> List[List[DeviationPoint]]:
    """识别连续超限的区段。

    连续超限定义为相邻超限点的索引差为 1。

    Args:
        deviation_points: 超限点位列表（已按索引排序）
        consecutive_count: 连续超限判定次数

    Returns:
        连续超限区段列表，每个区段包含至少 consecutive_count 个连续超限点
    """
    if not deviation_points:
        return []

    segments: List[List[DeviationPoint]] = []
    current_segment: List[DeviationPoint] = [deviation_points[0]]

    for dp in deviation_points[1:]:
        if dp.index == current_segment[-1].index + 1:
            current_segment.append(dp)
        else:
            if len(current_segment) >= consecutive_count:
                segments.append(current_segment)
            current_segment = [dp]

    if len(current_segment) >= consecutive_count:
        segments.append(current_segment)

    return segments


def _determine_severity(
    deviation_points: List[DeviationPoint],
    consecutive_count: int,
) -> str:
    """根据超限情况判定严重程度。

    Args:
        deviation_points: 超限点位列表
        consecutive_count: 连续超限判定次数

    Returns:
        "CRITICAL" 或 "WARNING"
    """
    if len(deviation_points) >= consecutive_count * 2:
        return "CRITICAL"
    return "WARNING"


# ──────────────────────────────────────────────────────────────
# Mock 数据生成（用于历史分析）
# ──────────────────────────────────────────────────────────────


def _generate_mock_measurements(
    test_item_id: str,
    start_date: str,
    end_date: str,
    target_value: float = 5.5,
    sd_value: float = 0.3,
) -> List[float]:
    """生成模拟的测量数据用于历史分析。

    生成以 target_value 为中心、sd_value 为标准差的正态分布随机数，
    并模拟一定的漂移趋势。

    Args:
        test_item_id: 诊疗项目ID
        start_date: 起始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        target_value: 目标值
        sd_value: 标准差

    Returns:
        模拟测量值列表
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        start = datetime.now() - timedelta(days=30)
        end = datetime.now()

    days = max((end - start).days, 1)
    # 假设每天 4 个测量点
    num_points = days * 4

    rng = np.random.default_rng(seed=hash(test_item_id) % (2**31))
    # 基础随机噪声
    noise = rng.normal(0, sd_value, num_points)
    # 模拟缓慢漂移（正弦波趋势）
    trend = 0.3 * np.sin(np.linspace(0, 2 * np.pi, num_points))
    measurements = target_value + noise + trend

    return measurements.tolist()


# ──────────────────────────────────────────────────────────────
# 分析服务
# ──────────────────────────────────────────────────────────────


class AnomalyAnalyzer:
    """异常预警分析服务。

    封装实时分析与历史分析两种场景的业务逻辑。
    """

    def __init__(self, java_client: Optional[JavaApiClient] = None) -> None:
        self._java_client = java_client or JavaApiClient()

    async def analyze_realtime(
        self,
        test_item_id: str,
        measurements: List[float],
    ) -> AnomalyResult:
        """实时分析：获取规则 → 计算路径依从率 → 检测超限 → 上报异常。

        Args:
            test_item_id: 诊疗项目ID
            measurements: 最新的测量值序列

        Returns:
            AnomalyResult: 分析结果
        """
        logger.info(
            "Starting realtime analysis for test_item_id=%s, data_points=%d",
            test_item_id, len(measurements),
        )

        # 1. 调用 Java 端获取预警规则
        try:
            rule = await self._java_client.get_anomaly_rule(test_item_id)
            logger.debug(
                "Got rule: window_size=%d, consecutive_count=%d, "
                "threshold_multiplier=%.2f, target=%.4f, sd=%.4f",
                rule.window_size, rule.consecutive_count,
                rule.threshold_multiplier, rule.target_value, rule.sd_value,
            )
        except JavaApiClientNotFoundError:
            logger.warning(
                "No anomaly rule found for test_item_id=%s", test_item_id,
            )
            return AnomalyResult(
                test_item_id=test_item_id,
                triggered=False,
                moving_averages=[],
                deviation_points=[],
                consecutive_count=0,
                message="未配置预警规则",
            )
        except Exception as e:
            logger.error(
                "Failed to fetch anomaly rule for %s: %s", test_item_id, e,
            )
            return AnomalyResult(
                test_item_id=test_item_id,
                triggered=False,
                moving_averages=[],
                deviation_points=[],
                consecutive_count=0,
                message=f"获取预警规则失败: {str(e)}",
            )

        # 2. 计算路径依从率
        try:
            moving_averages = compute_moving_averages(
                measurements, rule.window_size,
            )
        except ValueError as e:
            logger.error("Failed to compute moving averages: %s", e)
            return AnomalyResult(
                test_item_id=test_item_id,
                triggered=False,
                moving_averages=[],
                deviation_points=[],
                consecutive_count=0,
                message=f"计算路径依从率失败: {str(e)}",
            )

        # 3. 检测超限点
        deviation_points = detect_deviationes(
            moving_averages,
            target=rule.target_value,
            sd=rule.sd_value,
            threshold_multiplier=rule.threshold_multiplier,
        )

        # 4. 判定是否连续 N 次超限
        segments = _find_consecutive_segments(
            deviation_points, rule.consecutive_count,
        )
        triggered = len(segments) > 0
        consecutive = 0
        if triggered:
            consecutive = len(segments[0])

        severity = _determine_severity(deviation_points, rule.consecutive_count) if triggered else None

        # 5. 如果触发异常预警，调用 Java 端记录异常事件
        event_id: Optional[int] = None
        if triggered:
            try:
                event_request = AnomalyEventCreateRequest(
                    rule_id=rule.id,
                    test_item_id=test_item_id,
                    triggered_at=datetime.now().isoformat(),
                    severity=severity or "WARNING",
                    moving_averages=moving_averages,
                    deviation_points=deviation_points,
                    message=(
                        f"检测到 {len(segments)} 个异常预警区段，"
                        f"最大连续超限 {consecutive} 次"
                    ),
                )
                event_response = await self._java_client.create_anomaly_event(
                    event_request,
                )
                event_id = event_response.id
                logger.warning(
                    "Anomaly triggered for %s, event_id=%d, severity=%s",
                    test_item_id, event_id, severity,
                )
            except Exception as e:
                logger.error(
                    "Failed to create anomaly event for %s: %s",
                    test_item_id, e,
                )

        return AnomalyResult(
            test_item_id=test_item_id,
            triggered=triggered,
            moving_averages=moving_averages,
            deviation_points=deviation_points,
            consecutive_count=consecutive,
            severity=severity,
            event_id=event_id,
            message=(
                f"分析完成，共 {len(deviation_points)} 个超限点，"
                f"{len(segments)} 个异常预警区段"
                if triggered else "未触发异常预警"
            ),
        )

    async def analyze_history(
        self,
        test_item_id: str,
        start_date: str,
        end_date: str,
        custom_params: Optional[Dict[str, Any]] = None,
    ) -> HistoryAnalysis:
        """历史分析：获取历史数据 → 计算路径依从率 → 检测超限 → 生成摘要。

        Args:
            test_item_id: 诊疗项目ID
            start_date: 分析起始日期 (YYYY-MM-DD)
            end_date: 分析结束日期 (YYYY-MM-DD)
            custom_params: 可选的自定义参数（用于回测），支持：
                - window_size: 路径依从率窗口大小
                - consecutive_count: 连续超限判定次数
                - threshold_multiplier: 控制限倍数
                - target_value: 目标值
                - sd_value: 标准差

        Returns:
            HistoryAnalysis: 历史分析结果
        """
        logger.info(
            "Starting history analysis for test_item_id=%s, "
            "start=%s, end=%s",
            test_item_id, start_date, end_date,
        )

        params = custom_params or {}

        # 1. 尝试从 Java 端获取规则，或使用自定义参数/默认值
        window_size: int = params.get("window_size", 5)
        consecutive_count: int = params.get("consecutive_count", 3)
        threshold_multiplier: float = params.get("threshold_multiplier", 1.5)
        target_value: float = params.get("target_value", 5.5)
        sd_value: float = params.get("sd_value", 0.3)

        try:
            rule = await self._java_client.get_anomaly_rule(test_item_id)
            window_size = rule.window_size
            consecutive_count = rule.consecutive_count
            threshold_multiplier = rule.threshold_multiplier
            target_value = rule.target_value
            sd_value = rule.sd_value
            logger.debug("Using rule from Java backend for %s", test_item_id)
        except JavaApiClientNotFoundError:
            logger.info(
                "No rule found for %s, using custom/default parameters",
                test_item_id,
            )
        except Exception as e:
            logger.warning(
                "Failed to fetch rule for %s, using defaults: %s",
                test_item_id, e,
            )

        # 2. 获取历史数据（mock 数据生成器）
        measurements = _generate_mock_measurements(
            test_item_id, start_date, end_date,
            target_value=target_value,
            sd_value=sd_value,
        )

        # 3. 计算路径依从率
        moving_averages = compute_moving_averages(measurements, window_size)

        # 4. 检测所有超限点
        deviation_points = detect_deviationes(
            moving_averages,
            target=target_value,
            sd=sd_value,
            threshold_multiplier=threshold_multiplier,
        )

        # 5. 识别异常预警区段
        segments_raw = _find_consecutive_segments(
            deviation_points, consecutive_count,
        )

        segments: List[AnomalySegment] = []
        for seg in segments_raw:
            max_dev = max(
                abs(dp.moving_average - target_value) for dp in seg
            )
            seg_severity = "CRITICAL" if len(seg) >= consecutive_count * 2 else "WARNING"
            segments.append(AnomalySegment(
                start_index=seg[0].index,
                end_index=seg[-1].index,
                deviation_count=len(seg),
                max_deviation=max_dev,
                severity=seg_severity,
            ))

        # 6. 生成统计摘要
        summary: Dict[str, Any] = {
            "total_points": len(measurements),
            "total_deviation_points": len(deviation_points),
            "total_segments": len(segments),
            "window_size": window_size,
            "consecutive_count": consecutive_count,
            "threshold_multiplier": threshold_multiplier,
            "target_value": target_value,
            "sd_value": sd_value,
            "mean_value": float(np.mean(measurements)),
            "std_value": float(np.std(measurements, ddof=1)) if len(measurements) > 1 else 0.0,
            "min_value": float(np.min(measurements)),
            "max_value": float(np.max(measurements)),
            "parameters_source": "rule" if "rule" in dir() and rule else "custom",
        }

        return HistoryAnalysis(
            test_item_id=test_item_id,
            start_date=start_date,
            end_date=end_date,
            data_points=len(measurements),
            moving_averages=moving_averages,
            deviation_points=deviation_points,
            segments=segments,
            summary=summary,
        )

    async def close(self) -> None:
        """关闭底层 HTTP 客户端。"""
        await self._java_client.close()
