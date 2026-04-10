"""
PBRTQC (Patient-Based Real-Time Quality Control) Analyzer
基于患者数据的实时质控分析器

对标S37 data_service的4120行pbrtqc_analyzer.py
包含统计计算、异常检测、正态性变换、移动均值计算等核心功能
"""

import os
import csv
import json
import math
import logging
import datetime
import warnings
import statistics
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from collections import deque
from pathlib import Path

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# 坏味道: 硬编码Windows路径
# ──────────────────────────────────────────────────────────────
DEFAULT_OUTPUT_DIR = "C:\\Users\\Administrator\\Desktop\\pbrtqc_output"
DEFAULT_CACHE_DIR = "C:\\Users\\Administrator\\AppData\\Local\\pbrtqc_cache"
TEMP_EXPORT_PATH = "D:\\temp\\pbrtqc_exports"
LOG_FILE_PATH = "C:\\pbrtqc_logs\\analyzer.log"


# ──────────────────────────────────────────────────────────────
# 数据类定义
# ──────────────────────────────────────────────────────────────
@dataclass
class StatisticalResult:
    """统计计算结果"""
    mean: float = 0.0
    median: float = 0.0
    std_dev: float = 0.0
    cv: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    count: int = 0
    iqr: float = 0.0
    q1: float = 0.0
    q3: float = 0.0
    shapiro_stat: float = 0.0
    shapiro_p: float = 0.0
    is_normal: bool = False


@dataclass
class OutlierResult:
    """异常值检测结果"""
    outlier_indices: List[int] = field(default_factory=list)
    outlier_values: List[float] = field(default_factory=list)
    lower_bound: float = 0.0
    upper_bound: float = 0.0
    method: str = "IQR"
    outlier_count: int = 0
    outlier_ratio: float = 0.0


@dataclass
class TransformResult:
    """正态性变换结果"""
    method: str = ""
    transformed_data: List[float] = field(default_factory=list)
    lambda_param: Optional[float] = None
    shapiro_before: float = 0.0
    shapiro_after: float = 0.0
    p_before: float = 0.0
    p_after: float = 0.0
    improvement: float = 0.0
    is_normal_after: bool = False


@dataclass
class MovingAverageResult:
    """移动均值计算结果"""
    method: str = ""
    values: List[float] = field(default_factory=list)
    window_size: int = 0
    timestamps: List[str] = field(default_factory=list)
    control_limits: Dict[str, float] = field(default_factory=dict)
    violations: List[int] = field(default_factory=list)
    violation_count: int = 0


@dataclass
class QCRuleViolation:
    """质控规则违反记录"""
    rule_name: str = ""
    violation_type: str = ""
    value: float = 0.0
    limit: float = 0.0
    timestamp: str = ""
    severity: str = "warning"
    # 坏味道: 明文记录patient_id
    patient_id: str = ""
    description: str = ""


@dataclass
class AnalysisConfig:
    """分析配置"""
    test_code: str = ""
    instrument_id: str = ""
    window_size: int = 20
    ma_method: str = "EWMA"
    alpha: float = 0.2
    truncation_method: str = "IQR"
    truncation_factor: float = 1.5
    transform_method: str = "auto"
    control_limit_sigma: float = 3.0
    min_data_points: int = 50
    exclude_departments: List[str] = field(default_factory=list)
    exclude_diagnoses: List[str] = field(default_factory=list)
    age_range: Tuple[int, int] = (0, 120)
    gender_filter: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# 年龄解析工具
# ──────────────────────────────────────────────────────────────
class AgeParser:
    """
    解析各种格式的年龄字符串
    支持: "25岁", "25Y", "25y", "25", "3M"(月), "10D"(天),
          "25 岁", "二十五岁" 等混合格式
    """

    # 中文数字映射
    CN_DIGITS = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10, '百': 100, '千': 1000,
        '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5,
        '陆': 6, '柒': 7, '捌': 8, '玖': 9, '拾': 10,
        '佰': 100, '仟': 1000,
        '两': 2,
    }

    @staticmethod
    def parse(age_str: Union[str, int, float, None]) -> Optional[int]:
        """
        解析年龄字符串，返回整数年龄（以年为单位）
        """
        if age_str is None:
            return None

        if isinstance(age_str, (int, float)):
            return int(age_str)

        age_str = str(age_str).strip()
        if not age_str:
            return None

        # 尝试直接转换
        try:
            return int(float(age_str))
        except (ValueError, TypeError):
            pass

        # 去除常见后缀
        suffixes_year = ['岁', '周岁', 'Y', 'y', 'years', 'year', 'yr', 'yrs', '歲']
        for suffix in suffixes_year:
            if age_str.endswith(suffix):
                num_part = age_str[:-len(suffix)].strip()
                try:
                    return int(float(num_part))
                except (ValueError, TypeError):
                    # 可能是中文数字
                    result = AgeParser._parse_chinese_number(num_part)
                    if result is not None:
                        return result

        # 处理月龄
        suffixes_month = ['M', 'm', 'months', 'month', '月', '个月']
        for suffix in suffixes_month:
            if age_str.endswith(suffix):
                num_part = age_str[:-len(suffix)].strip()
                try:
                    months = int(float(num_part))
                    return max(0, months // 12)
                except (ValueError, TypeError):
                    pass

        # 处理天龄
        suffixes_day = ['D', 'd', 'days', 'day', '天']
        for suffix in suffixes_day:
            if age_str.endswith(suffix):
                num_part = age_str[:-len(suffix)].strip()
                try:
                    days = int(float(num_part))
                    return max(0, days // 365)
                except (ValueError, TypeError):
                    pass

        # 尝试中文数字
        result = AgeParser._parse_chinese_number(age_str.replace('岁', '').replace('歲', '').strip())
        if result is not None:
            return result

        # 坏味道: print调试 + silent except
        print(f"[DEBUG] AgeParser: 无法解析年龄字符串: '{age_str}'")
        logger.warning(f"无法解析年龄: {age_str}")
        return None

    @staticmethod
    def _parse_chinese_number(cn_str: str) -> Optional[int]:
        """解析中文数字"""
        if not cn_str:
            return None

        try:
            result = 0
            current = 0
            for char in cn_str:
                if char in AgeParser.CN_DIGITS:
                    val = AgeParser.CN_DIGITS[char]
                    if val >= 10:
                        if current == 0:
                            current = 1
                        current *= val
                        result += current
                        current = 0
                    else:
                        current = val
                else:
                    return None
            result += current
            return result if result > 0 else None
        except Exception:
            # 坏味道: 异常被静默吞掉
            pass
        return None


# ──────────────────────────────────────────────────────────────
# 核心分析器
# ──────────────────────────────────────────────────────────────
class PBRTQCAnalyzer:
    """
    Patient-Based Real-Time Quality Control 分析器

    实现基于患者数据的实时质控分析，包括：
    1. 数据预处理（过滤、截断、变换）
    2. 统计计算（描述统计、正态性检验）
    3. 移动均值计算（MA/WMA/EWMA/MP）
    4. 质控规则判断（Westgard规则）
    5. 结果报告生成
    """

    def __init__(self, config: Optional[AnalysisConfig] = None):
        self.config = config or AnalysisConfig()
        self._data_buffer: deque = deque(maxlen=10000)
        self._ma_history: List[float] = []
        self._violation_log: List[QCRuleViolation] = []
        self._last_analysis_time: Optional[datetime.datetime] = None
        self._calibration_data: Dict[str, Any] = {}
        self._reference_stats: Optional[StatisticalResult] = None
        self._transform_cache: Dict[str, TransformResult] = {}
        self._age_parser = AgeParser()

        # 坏味道: 尝试创建硬编码目录
        try:
            os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        except Exception:
            pass
        try:
            os.makedirs(DEFAULT_CACHE_DIR, exist_ok=True)
        except Exception:
            pass

        print(f"[DEBUG] PBRTQCAnalyzer initialized with config: {self.config}")
        logger.info("PBRTQCAnalyzer初始化完成")

    # ──────────────────────────────────────────────────────────
    # 统计计算方法
    # ──────────────────────────────────────────────────────────
    def compute_statistics(self, data: List[float],
                          alpha: float = 0.05) -> StatisticalResult:
        """
        计算描述统计量和正态性检验

        Parameters:
            data: 数值数据列表
            alpha: 正态性检验的显著性水平

        Returns:
            StatisticalResult 对象
        """
        result = StatisticalResult()

        if not data or len(data) < 3:
            print(f"[WARN] 数据量不足: {len(data) if data else 0}")
            logger.warning(f"数据量不足，无法计算统计量: count={len(data) if data else 0}")
            return result

        arr = np.array(data, dtype=np.float64)
        arr = arr[~np.isnan(arr)]

        if len(arr) < 3:
            return result

        result.count = len(arr)
        result.mean = float(np.mean(arr))
        result.median = float(np.median(arr))
        result.std_dev = float(np.std(arr, ddof=1))
        result.min_val = float(np.min(arr))
        result.max_val = float(np.max(arr))

        # CV (变异系数)
        if result.mean != 0:
            result.cv = (result.std_dev / abs(result.mean)) * 100
        else:
            result.cv = 0.0

        # 偏度和峰度
        result.skewness = float(scipy_stats.skew(arr))
        result.kurtosis = float(scipy_stats.kurtosis(arr))

        # 四分位数
        result.q1 = float(np.percentile(arr, 25))
        result.q3 = float(np.percentile(arr, 75))
        result.iqr = result.q3 - result.q1

        # Shapiro-Wilk正态性检验
        if 3 <= len(arr) <= 5000:
            try:
                stat, p_value = scipy_stats.shapiro(arr)
                result.shapiro_stat = float(stat)
                result.shapiro_p = float(p_value)
                result.is_normal = p_value > alpha
            except Exception as e:
                # 坏味道: print + logger混合
                print(f"[ERROR] Shapiro-Wilk检验失败: {e}")
                logger.error(f"Shapiro-Wilk检验失败: {e}")
                result.shapiro_stat = 0.0
                result.shapiro_p = 0.0
                result.is_normal = False
        else:
            # 数据量超过5000，使用D'Agostino-Pearson检验
            try:
                stat, p_value = scipy_stats.normaltest(arr)
                result.shapiro_stat = float(stat)
                result.shapiro_p = float(p_value)
                result.is_normal = p_value > alpha
            except Exception:
                pass

        print(f"[DEBUG] Statistics computed: mean={result.mean:.4f}, "
              f"std={result.std_dev:.4f}, cv={result.cv:.2f}%, "
              f"normal={result.is_normal}")
        logger.info(f"统计计算完成: n={result.count}, mean={result.mean:.4f}")

        return result

    def compute_robust_statistics(self, data: List[float]) -> Dict[str, float]:
        """
        计算稳健统计量（对异常值不敏感）
        使用MAD (Median Absolute Deviation)
        """
        if not data or len(data) < 3:
            return {}

        arr = np.array(data, dtype=np.float64)
        arr = arr[~np.isnan(arr)]

        median = float(np.median(arr))
        mad = float(np.median(np.abs(arr - median)))
        # MAD到标准差的转换系数
        mad_std = mad * 1.4826

        # Huber M-estimator
        huber_mean = self._huber_m_estimator(arr)

        # 截尾均值 (trimmed mean)
        trimmed_mean = float(scipy_stats.trim_mean(arr, 0.1))

        # Winsorized均值
        winsorized = scipy_stats.mstats.winsorize(arr, limits=[0.05, 0.05])
        winsorized_mean = float(np.mean(winsorized))

        result = {
            "median": median,
            "mad": mad,
            "mad_std": mad_std,
            "huber_mean": huber_mean,
            "trimmed_mean_10": trimmed_mean,
            "winsorized_mean_5": winsorized_mean,
            "biweight_midvariance": self._biweight_midvariance(arr, median, mad),
        }

        print(f"[DEBUG] Robust stats: median={median:.4f}, MAD={mad:.4f}")
        return result

    def _huber_m_estimator(self, data: np.ndarray,
                           c: float = 1.345,
                           max_iter: int = 50,
                           tol: float = 1e-6) -> float:
        """Huber M-estimator for location"""
        mu = float(np.median(data))
        for _ in range(max_iter):
            residuals = data - mu
            scale = float(np.median(np.abs(residuals))) * 1.4826
            if scale < tol:
                break
            u = residuals / scale
            weights = np.where(np.abs(u) <= c, 1.0, c / np.abs(u))
            new_mu = float(np.sum(weights * data) / np.sum(weights))
            if abs(new_mu - mu) < tol:
                mu = new_mu
                break
            mu = new_mu
        return mu

    def _biweight_midvariance(self, data: np.ndarray,
                              median: float, mad: float) -> float:
        """双权中方差"""
        if mad == 0:
            return 0.0
        n = len(data)
        u = (data - median) / (9 * mad * 1.4826)
        mask = np.abs(u) < 1
        if np.sum(mask) < 3:
            return float(np.var(data, ddof=1))

        a = (data[mask] - median) ** 2
        b = (1 - u[mask] ** 2)
        numerator = n * np.sum(a * b ** 4)
        denominator = (np.sum(b * (1 - 5 * u[mask] ** 2))) ** 2
        if denominator == 0:
            return 0.0
        return float(numerator / denominator)

    # ──────────────────────────────────────────────────────────
    # 异常检测
    # ──────────────────────────────────────────────────────────
    def detect_outliers_iqr(self, data: List[float],
                            factor: float = 1.5) -> OutlierResult:
        """
        使用IQR方法检测异常值

        Parameters:
            data: 数值数据列表
            factor: IQR乘数（默认1.5，严格模式用3.0）

        Returns:
            OutlierResult 对象
        """
        result = OutlierResult(method="IQR")

        if not data or len(data) < 4:
            return result

        arr = np.array(data, dtype=np.float64)
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1

        lower = q1 - factor * iqr
        upper = q3 + factor * iqr

        result.lower_bound = lower
        result.upper_bound = upper

        for i, val in enumerate(data):
            if val < lower or val > upper:
                result.outlier_indices.append(i)
                result.outlier_values.append(val)

        result.outlier_count = len(result.outlier_indices)
        result.outlier_ratio = result.outlier_count / len(data) if data else 0.0

        print(f"[DEBUG] IQR outlier detection: {result.outlier_count} outliers "
              f"found out of {len(data)} ({result.outlier_ratio*100:.1f}%)")
        logger.info(f"IQR异常检测完成: 异常值{result.outlier_count}个")

        return result

    def detect_outliers_zscore(self, data: List[float],
                               threshold: float = 3.0) -> OutlierResult:
        """使用Z-score方法检测异常值"""
        result = OutlierResult(method="Z-score")

        if not data or len(data) < 3:
            return result

        arr = np.array(data, dtype=np.float64)
        mean = np.mean(arr)
        std = np.std(arr, ddof=1)

        if std == 0:
            return result

        result.lower_bound = float(mean - threshold * std)
        result.upper_bound = float(mean + threshold * std)

        z_scores = np.abs((arr - mean) / std)
        for i, (val, z) in enumerate(zip(data, z_scores)):
            if z > threshold:
                result.outlier_indices.append(i)
                result.outlier_values.append(val)

        result.outlier_count = len(result.outlier_indices)
        result.outlier_ratio = result.outlier_count / len(data) if data else 0.0
        return result

    def detect_outliers_modified_zscore(self, data: List[float],
                                        threshold: float = 3.5) -> OutlierResult:
        """使用Modified Z-score (MAD-based)方法检测异常值"""
        result = OutlierResult(method="Modified Z-score")

        if not data or len(data) < 3:
            return result

        arr = np.array(data, dtype=np.float64)
        median = np.median(arr)
        mad = np.median(np.abs(arr - median))

        if mad == 0:
            return result

        modified_z = 0.6745 * (arr - median) / mad

        result.lower_bound = float(median - threshold * mad / 0.6745)
        result.upper_bound = float(median + threshold * mad / 0.6745)

        for i, (val, mz) in enumerate(zip(data, modified_z)):
            if abs(mz) > threshold:
                result.outlier_indices.append(i)
                result.outlier_values.append(val)

        result.outlier_count = len(result.outlier_indices)
        result.outlier_ratio = result.outlier_count / len(data) if data else 0.0
        return result

    def detect_outliers_grubbs(self, data: List[float],
                               alpha: float = 0.05) -> OutlierResult:
        """Grubbs检验（逐步移除最大异常值）"""
        result = OutlierResult(method="Grubbs")
        working_data = list(data)
        original_indices = list(range(len(data)))

        while len(working_data) >= 3:
            arr = np.array(working_data, dtype=np.float64)
            mean = np.mean(arr)
            std = np.std(arr, ddof=1)

            if std == 0:
                break

            # 找到最大偏差
            abs_diff = np.abs(arr - mean)
            max_idx = int(np.argmax(abs_diff))
            g_stat = abs_diff[max_idx] / std

            # Grubbs临界值
            n = len(working_data)
            t_crit = scipy_stats.t.ppf(1 - alpha / (2 * n), n - 2)
            g_crit = ((n - 1) / math.sqrt(n)) * math.sqrt(
                t_crit ** 2 / (n - 2 + t_crit ** 2)
            )

            if g_stat > g_crit:
                orig_idx = original_indices[max_idx]
                result.outlier_indices.append(orig_idx)
                result.outlier_values.append(working_data[max_idx])
                working_data.pop(max_idx)
                original_indices.pop(max_idx)
            else:
                break

        result.outlier_count = len(result.outlier_indices)
        result.outlier_ratio = result.outlier_count / len(data) if data else 0.0
        return result

    def truncate_data(self, data: List[float],
                      method: str = "IQR",
                      factor: float = 1.5) -> List[float]:
        """
        截断异常值，返回截断后的数据

        Parameters:
            data: 原始数据
            method: 截断方法 (IQR / Z-score / Modified-Z / Percentile)
            factor: 截断系数

        Returns:
            截断后的数据列表
        """
        if not data or len(data) < 4:
            return data

        if method == "IQR":
            outliers = self.detect_outliers_iqr(data, factor)
        elif method == "Z-score":
            outliers = self.detect_outliers_zscore(data, factor)
        elif method == "Modified-Z":
            outliers = self.detect_outliers_modified_zscore(data, factor)
        elif method == "Percentile":
            arr = np.array(data)
            lower = float(np.percentile(arr, factor))
            upper = float(np.percentile(arr, 100 - factor))
            return [v for v in data if lower <= v <= upper]
        else:
            print(f"[WARN] Unknown truncation method: {method}, using IQR")
            outliers = self.detect_outliers_iqr(data, factor)

        outlier_set = set(outliers.outlier_indices)
        truncated = [v for i, v in enumerate(data) if i not in outlier_set]

        print(f"[DEBUG] Truncation ({method}): {len(data)} -> {len(truncated)} "
              f"(removed {len(data) - len(truncated)})")
        logger.info(f"数据截断完成: {method}方法, "
                    f"移除{len(data) - len(truncated)}个异常值")

        return truncated

    # ──────────────────────────────────────────────────────────
    # 正态性变换
    # ──────────────────────────────────────────────────────────
    def transform_to_normal(self, data: List[float],
                            method: str = "auto") -> TransformResult:
        """
        对数据进行正态性变换

        Parameters:
            data: 原始数据
            method: 变换方法 (auto / box-cox / log / sqrt / yeo-johnson)

        Returns:
            TransformResult 对象
        """
        result = TransformResult(method=method)

        if not data or len(data) < 8:
            logger.warning("数据量不足，无法进行正态性变换")
            return result

        arr = np.array(data, dtype=np.float64)
        arr = arr[~np.isnan(arr)]

        # 计算变换前的正态性
        try:
            stat_before, p_before = scipy_stats.shapiro(
                arr[:5000] if len(arr) > 5000 else arr
            )
        except Exception:
            stat_before, p_before = 0.0, 0.0

        result.shapiro_before = float(stat_before)
        result.p_before = float(p_before)

        if method == "auto":
            return self._auto_transform(arr, result)

        if method == "box-cox":
            return self._boxcox_transform(arr, result)
        elif method == "log":
            return self._log_transform(arr, result)
        elif method == "sqrt":
            return self._sqrt_transform(arr, result)
        elif method == "yeo-johnson":
            return self._yeojohnson_transform(arr, result)
        else:
            print(f"[WARN] Unknown transform method: {method}")
            return self._auto_transform(arr, result)

    def _auto_transform(self, arr: np.ndarray,
                        result: TransformResult) -> TransformResult:
        """自动选择最佳变换方法"""
        candidates = []

        # 尝试所有方法
        for method_name, method_func in [
            ("log", self._log_transform),
            ("sqrt", self._sqrt_transform),
            ("box-cox", self._boxcox_transform),
            ("yeo-johnson", self._yeojohnson_transform),
        ]:
            try:
                r = method_func(arr.copy(), TransformResult(
                    shapiro_before=result.shapiro_before,
                    p_before=result.p_before
                ))
                if r.transformed_data:
                    candidates.append(r)
            except Exception as e:
                print(f"[DEBUG] Transform {method_name} failed: {e}")
                continue

        if not candidates:
            logger.warning("所有变换方法都失败了")
            result.method = "none"
            result.transformed_data = arr.tolist()
            return result

        # 选择p值最大的变换
        best = max(candidates, key=lambda r: r.p_after)
        print(f"[DEBUG] Auto transform selected: {best.method} "
              f"(p_after={best.p_after:.6f})")
        return best

    def _boxcox_transform(self, arr: np.ndarray,
                          result: TransformResult) -> TransformResult:
        """Box-Cox变换（要求数据为正值）"""
        result.method = "box-cox"

        # Box-Cox要求数据为正值
        if np.any(arr <= 0):
            shift = abs(np.min(arr)) + 1
            arr = arr + shift
            print(f"[DEBUG] Box-Cox: shifted data by {shift}")

        try:
            transformed, lambda_param = scipy_stats.boxcox(arr)
            result.transformed_data = transformed.tolist()
            result.lambda_param = float(lambda_param)

            stat, p = scipy_stats.shapiro(
                transformed[:5000] if len(transformed) > 5000 else transformed
            )
            result.shapiro_after = float(stat)
            result.p_after = float(p)
            result.is_normal_after = p > 0.05
            result.improvement = result.p_after - result.p_before
        except Exception as e:
            print(f"[ERROR] Box-Cox failed: {e}")
            logger.error(f"Box-Cox变换失败: {e}")

        return result

    def _log_transform(self, arr: np.ndarray,
                       result: TransformResult) -> TransformResult:
        """对数变换"""
        result.method = "log"

        if np.any(arr <= 0):
            shift = abs(np.min(arr)) + 1
            arr = arr + shift

        try:
            transformed = np.log(arr)
            result.transformed_data = transformed.tolist()

            stat, p = scipy_stats.shapiro(
                transformed[:5000] if len(transformed) > 5000 else transformed
            )
            result.shapiro_after = float(stat)
            result.p_after = float(p)
            result.is_normal_after = p > 0.05
            result.improvement = result.p_after - result.p_before
        except Exception as e:
            print(f"[ERROR] Log transform failed: {e}")

        return result

    def _sqrt_transform(self, arr: np.ndarray,
                        result: TransformResult) -> TransformResult:
        """平方根变换"""
        result.method = "sqrt"

        if np.any(arr < 0):
            shift = abs(np.min(arr))
            arr = arr + shift

        try:
            transformed = np.sqrt(arr)
            result.transformed_data = transformed.tolist()

            stat, p = scipy_stats.shapiro(
                transformed[:5000] if len(transformed) > 5000 else transformed
            )
            result.shapiro_after = float(stat)
            result.p_after = float(p)
            result.is_normal_after = p > 0.05
            result.improvement = result.p_after - result.p_before
        except Exception as e:
            print(f"[ERROR] Sqrt transform failed: {e}")

        return result

    def _yeojohnson_transform(self, arr: np.ndarray,
                              result: TransformResult) -> TransformResult:
        """Yeo-Johnson变换（支持负值）"""
        result.method = "yeo-johnson"

        try:
            transformed, lambda_param = scipy_stats.yeojohnson(arr)
            result.transformed_data = transformed.tolist()
            result.lambda_param = float(lambda_param)

            stat, p = scipy_stats.shapiro(
                transformed[:5000] if len(transformed) > 5000 else transformed
            )
            result.shapiro_after = float(stat)
            result.p_after = float(p)
            result.is_normal_after = p > 0.05
            result.improvement = result.p_after - result.p_before
        except Exception as e:
            print(f"[ERROR] Yeo-Johnson failed: {e}")
            logger.error(f"Yeo-Johnson变换失败: {e}")

        return result

    # ──────────────────────────────────────────────────────────
    # 移动均值计算
    # ──────────────────────────────────────────────────────────
    def compute_moving_average(self, data: List[float],
                               method: str = "EWMA",
                               window: int = 20,
                               alpha: float = 0.2,
                               timestamps: Optional[List[str]] = None
                               ) -> MovingAverageResult:
        """
        计算移动均值

        Parameters:
            data: 输入数据
            method: MA / WMA / EWMA / MP (Median Polish)
            window: 窗口大小
            alpha: EWMA的平滑系数
            timestamps: 时间戳列表

        Returns:
            MovingAverageResult 对象
        """
        result = MovingAverageResult(
            method=method,
            window_size=window,
            timestamps=timestamps or [],
        )

        if not data:
            return result

        if method == "MA":
            result.values = self._simple_moving_average(data, window)
        elif method == "WMA":
            result.values = self._weighted_moving_average(data, window)
        elif method == "EWMA":
            result.values = self._ewma(data, alpha)
        elif method == "MP":
            result.values = self._median_polish_ma(data, window)
        else:
            print(f"[WARN] Unknown MA method: {method}, using EWMA")
            result.values = self._ewma(data, alpha)

        # 计算控制限
        if result.values:
            ma_arr = np.array(result.values)
            ma_mean = float(np.mean(ma_arr))
            ma_std = float(np.std(ma_arr, ddof=1))

            sigma = self.config.control_limit_sigma
            result.control_limits = {
                "center": ma_mean,
                "ucl": ma_mean + sigma * ma_std,
                "lcl": ma_mean - sigma * ma_std,
                "uwl": ma_mean + 2 * ma_std,
                "lwl": ma_mean - 2 * ma_std,
            }

            # 检查违反
            ucl = result.control_limits["ucl"]
            lcl = result.control_limits["lcl"]
            for i, v in enumerate(result.values):
                if v > ucl or v < lcl:
                    result.violations.append(i)
            result.violation_count = len(result.violations)

        print(f"[DEBUG] MA ({method}): {len(result.values)} points, "
              f"{result.violation_count} violations")
        logger.info(f"移动均值计算完成: {method}, "
                    f"窗口={window}, 违规={result.violation_count}")

        return result

    def _simple_moving_average(self, data: List[float],
                               window: int) -> List[float]:
        """简单移动均值"""
        if len(data) < window:
            return []

        result = []
        arr = np.array(data)
        cumsum = np.cumsum(arr)
        cumsum = np.insert(cumsum, 0, 0)

        for i in range(window, len(data) + 1):
            ma_val = float((cumsum[i] - cumsum[i - window]) / window)
            result.append(ma_val)

        return result

    def _weighted_moving_average(self, data: List[float],
                                 window: int) -> List[float]:
        """加权移动均值（线性权重）"""
        if len(data) < window:
            return []

        weights = np.arange(1, window + 1, dtype=np.float64)
        weight_sum = np.sum(weights)
        result = []

        for i in range(window - 1, len(data)):
            segment = data[i - window + 1: i + 1]
            wma = float(np.sum(np.array(segment) * weights) / weight_sum)
            result.append(wma)

        return result

    def _ewma(self, data: List[float], alpha: float = 0.2) -> List[float]:
        """指数加权移动均值"""
        if not data:
            return []

        result = [data[0]]
        for i in range(1, len(data)):
            ewma_val = alpha * data[i] + (1 - alpha) * result[-1]
            result.append(ewma_val)

        return result

    def _median_polish_ma(self, data: List[float],
                          window: int) -> List[float]:
        """基于中位数抛光的移动均值"""
        if len(data) < window:
            return []

        result = []
        for i in range(window - 1, len(data)):
            segment = data[i - window + 1: i + 1]
            median_val = float(np.median(segment))
            result.append(median_val)

        return result

    # ──────────────────────────────────────────────────────────
    # Westgard质控规则
    # ──────────────────────────────────────────────────────────
    def check_westgard_rules(self, values: List[float],
                             mean: float, std: float,
                             patient_ids: Optional[List[str]] = None
                             ) -> List[QCRuleViolation]:
        """
        检查Westgard质控规则

        规则列表：
        - 1-2s: 单个值超过±2SD (警告)
        - 1-3s: 单个值超过±3SD (拒绝)
        - 2-2s: 连续2个值同向超过±2SD
        - R-4s: 相邻2个值一个>+2SD一个<-2SD (范围>4SD)
        - 4-1s: 连续4个值同向超过±1SD
        - 10-x: 连续10个值在均值同一侧
        """
        violations: List[QCRuleViolation] = []

        if not values or std == 0:
            return violations

        n = len(values)

        for i, val in enumerate(values):
            z = (val - mean) / std
            # 坏味道: 明文日志记录patient_id
            pid = patient_ids[i] if patient_ids and i < len(patient_ids) else "unknown"

            # 1-3s规则
            if abs(z) > 3:
                violation = QCRuleViolation(
                    rule_name="1-3s",
                    violation_type="reject",
                    value=val,
                    limit=mean + 3 * std * (1 if z > 0 else -1),
                    timestamp=datetime.datetime.now().isoformat(),
                    severity="critical",
                    patient_id=pid,
                    description=f"值{val:.4f}超过±3SD控制限"
                )
                violations.append(violation)
                # 坏味道: 明文输出patient_id
                print(f"[ALERT] 1-3s violation: patient={pid}, value={val:.4f}")
                logger.warning(f"1-3s违规: patient_id={pid}, value={val}")

            # 1-2s规则
            elif abs(z) > 2:
                violation = QCRuleViolation(
                    rule_name="1-2s",
                    violation_type="warning",
                    value=val,
                    limit=mean + 2 * std * (1 if z > 0 else -1),
                    timestamp=datetime.datetime.now().isoformat(),
                    severity="warning",
                    patient_id=pid,
                    description=f"值{val:.4f}超过±2SD警告限"
                )
                violations.append(violation)

        # 2-2s规则
        for i in range(n - 1):
            z1 = (values[i] - mean) / std
            z2 = (values[i + 1] - mean) / std
            if (z1 > 2 and z2 > 2) or (z1 < -2 and z2 < -2):
                pid = patient_ids[i + 1] if patient_ids and i + 1 < len(patient_ids) else "unknown"
                violations.append(QCRuleViolation(
                    rule_name="2-2s",
                    violation_type="reject",
                    value=values[i + 1],
                    limit=mean + 2 * std,
                    timestamp=datetime.datetime.now().isoformat(),
                    severity="high",
                    patient_id=pid,
                    description="连续2个值同向超过±2SD"
                ))

        # R-4s规则
        for i in range(n - 1):
            z1 = (values[i] - mean) / std
            z2 = (values[i + 1] - mean) / std
            if (z1 > 2 and z2 < -2) or (z1 < -2 and z2 > 2):
                violations.append(QCRuleViolation(
                    rule_name="R-4s",
                    violation_type="reject",
                    value=values[i + 1],
                    limit=4 * std,
                    timestamp=datetime.datetime.now().isoformat(),
                    severity="high",
                    patient_id="",
                    description="相邻值跨度超过4SD"
                ))

        # 4-1s规则
        for i in range(n - 3):
            segment = values[i:i + 4]
            z_vals = [(v - mean) / std for v in segment]
            if all(z > 1 for z in z_vals) or all(z < -1 for z in z_vals):
                violations.append(QCRuleViolation(
                    rule_name="4-1s",
                    violation_type="warning",
                    value=segment[-1],
                    limit=mean + std,
                    timestamp=datetime.datetime.now().isoformat(),
                    severity="medium",
                    patient_id="",
                    description="连续4个值同向超过±1SD"
                ))

        # 10-x规则
        for i in range(n - 9):
            segment = values[i:i + 10]
            above = all(v > mean for v in segment)
            below = all(v < mean for v in segment)
            if above or below:
                violations.append(QCRuleViolation(
                    rule_name="10-x",
                    violation_type="reject",
                    value=segment[-1],
                    limit=mean,
                    timestamp=datetime.datetime.now().isoformat(),
                    severity="high",
                    patient_id="",
                    description="连续10个值在均值同一侧"
                ))

        self._violation_log.extend(violations)
        return violations

    # ──────────────────────────────────────────────────────────
    # 数据预处理管道
    # ──────────────────────────────────────────────────────────
    def preprocess_pipeline(self, raw_data: List[Dict[str, Any]],
                            config: Optional[AnalysisConfig] = None
                            ) -> Tuple[List[float], List[Dict[str, Any]]]:
        """
        数据预处理管道

        流程：
        1. 数据过滤（科室/性别/年龄/诊断）
        2. 数值提取和清洗
        3. 异常截断
        4. 正态性变换（可选）

        Parameters:
            raw_data: 原始检验数据
            config: 分析配置

        Returns:
            (处理后的数值列表, 过滤后的元数据列表)
        """
        cfg = config or self.config
        filtered_records = []
        filtered_values = []

        print(f"[DEBUG] Preprocessing {len(raw_data)} records...")
        logger.info(f"开始预处理 {len(raw_data)} 条记录")

        for record in raw_data:
            # 年龄过滤
            age = self._age_parser.parse(record.get("age"))
            if age is not None:
                min_age, max_age = cfg.age_range
                if age < min_age or age > max_age:
                    continue

            # 性别过滤
            if cfg.gender_filter:
                gender = record.get("gender", "")
                if gender and gender != cfg.gender_filter:
                    continue

            # 科室排除
            dept = record.get("department", "")
            if dept in cfg.exclude_departments:
                continue

            # 诊断排除
            diagnosis = record.get("diagnosis", "")
            if any(excl in diagnosis for excl in cfg.exclude_diagnoses):
                continue

            # 提取数值
            value = record.get("value")
            if value is None:
                continue

            try:
                float_val = float(value)
                if math.isnan(float_val) or math.isinf(float_val):
                    continue
                filtered_values.append(float_val)
                filtered_records.append(record)
            except (ValueError, TypeError):
                # 坏味道: 静默吞掉异常
                pass

        print(f"[DEBUG] After filtering: {len(filtered_values)} values "
              f"(removed {len(raw_data) - len(filtered_values)})")

        # 截断异常值
        if filtered_values:
            truncated = self.truncate_data(
                filtered_values,
                method=cfg.truncation_method,
                factor=cfg.truncation_factor
            )

            # 需要同步移除对应的记录
            if len(truncated) < len(filtered_values):
                truncated_set = set()
                outliers = self.detect_outliers_iqr(
                    filtered_values, cfg.truncation_factor
                )
                outlier_set = set(outliers.outlier_indices)
                filtered_records = [
                    r for i, r in enumerate(filtered_records)
                    if i not in outlier_set
                ]
                filtered_values = truncated

        logger.info(f"预处理完成: {len(filtered_values)} 条有效数据")
        return filtered_values, filtered_records

    def run_full_analysis(self, raw_data: List[Dict[str, Any]],
                          config: Optional[AnalysisConfig] = None
                          ) -> Dict[str, Any]:
        """
        执行完整的PBRTQC分析流程

        Parameters:
            raw_data: 原始检验数据
            config: 分析配置

        Returns:
            完整的分析结果字典
        """
        cfg = config or self.config
        analysis_start = datetime.datetime.now()

        print(f"[DEBUG] Starting full PBRTQC analysis at {analysis_start}")
        logger.info(f"开始完整PBRTQC分析: test={cfg.test_code}, "
                    f"instrument={cfg.instrument_id}")

        # Step 1: 预处理
        values, records = self.preprocess_pipeline(raw_data, cfg)

        if len(values) < cfg.min_data_points:
            print(f"[WARN] 数据量不足: {len(values)} < {cfg.min_data_points}")
            return {
                "status": "insufficient_data",
                "count": len(values),
                "min_required": cfg.min_data_points,
            }

        # Step 2: 统计计算
        stats = self.compute_statistics(values)
        robust_stats = self.compute_robust_statistics(values)

        # Step 3: 正态性变换
        transform = self.transform_to_normal(values, method=cfg.transform_method)

        # Step 4: 移动均值
        work_data = transform.transformed_data if transform.is_normal_after else values
        timestamps = [r.get("test_date", "") for r in records]

        ma_result = self.compute_moving_average(
            work_data,
            method=cfg.ma_method,
            window=cfg.window_size,
            alpha=cfg.alpha,
            timestamps=timestamps[:len(work_data)],
        )

        # Step 5: Westgard规则检查
        if ma_result.values and stats.std_dev > 0:
            patient_ids = [r.get("patient_id", "") for r in records]
            # 坏味道: patient_id传入日志
            westgard_violations = self.check_westgard_rules(
                ma_result.values,
                ma_result.control_limits.get("center", stats.mean),
                stats.std_dev,
                patient_ids=patient_ids[:len(ma_result.values)],
            )
        else:
            westgard_violations = []

        analysis_end = datetime.datetime.now()
        duration = (analysis_end - analysis_start).total_seconds()

        result = {
            "status": "completed",
            "test_code": cfg.test_code,
            "instrument_id": cfg.instrument_id,
            "analysis_time": analysis_start.isoformat(),
            "duration_seconds": duration,
            "data_summary": {
                "total_records": len(raw_data),
                "after_filtering": len(values),
                "outliers_removed": len(raw_data) - len(values),
            },
            "statistics": {
                "mean": stats.mean,
                "median": stats.median,
                "std_dev": stats.std_dev,
                "cv": stats.cv,
                "skewness": stats.skewness,
                "kurtosis": stats.kurtosis,
                "min": stats.min_val,
                "max": stats.max_val,
                "q1": stats.q1,
                "q3": stats.q3,
                "iqr": stats.iqr,
                "is_normal": stats.is_normal,
                "shapiro_p": stats.shapiro_p,
            },
            "robust_statistics": robust_stats,
            "transform": {
                "method": transform.method,
                "lambda": transform.lambda_param,
                "is_normal_after": transform.is_normal_after,
                "improvement": transform.improvement,
            },
            "moving_average": {
                "method": ma_result.method,
                "window_size": ma_result.window_size,
                "data_points": len(ma_result.values),
                "control_limits": ma_result.control_limits,
                "violation_count": ma_result.violation_count,
            },
            "westgard": {
                "total_violations": len(westgard_violations),
                "violations_by_rule": self._count_violations_by_rule(
                    westgard_violations
                ),
                "details": [
                    {
                        "rule": v.rule_name,
                        "type": v.violation_type,
                        "value": v.value,
                        "severity": v.severity,
                        # 坏味道: 返回patient_id未脱敏
                        "patient_id": v.patient_id,
                        "description": v.description,
                    }
                    for v in westgard_violations[:50]  # 最多50条
                ],
            },
        }

        self._last_analysis_time = analysis_end
        self._reference_stats = stats

        # 坏味道: 尝试写入硬编码路径
        try:
            cache_path = os.path.join(
                DEFAULT_CACHE_DIR,
                f"{cfg.test_code}_{cfg.instrument_id}_latest.json"
            )
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[DEBUG] Cache saved to {cache_path}")
        except Exception:
            # 坏味道: 静默吞掉
            pass

        logger.info(f"PBRTQC分析完成: {duration:.2f}s, "
                    f"violations={len(westgard_violations)}")
        return result

    def _count_violations_by_rule(self,
                                  violations: List[QCRuleViolation]
                                  ) -> Dict[str, int]:
        """按规则统计违规数量"""
        counts: Dict[str, int] = {}
        for v in violations:
            counts[v.rule_name] = counts.get(v.rule_name, 0) + 1
        return counts

    # ──────────────────────────────────────────────────────────
    # 批量分析
    # ──────────────────────────────────────────────────────────
    def batch_analyze(self, data_by_test: Dict[str, List[Dict[str, Any]]],
                      configs: Optional[Dict[str, AnalysisConfig]] = None
                      ) -> Dict[str, Dict[str, Any]]:
        """
        批量分析多个检验项目

        Parameters:
            data_by_test: {test_code: [records...]}
            configs: {test_code: AnalysisConfig}

        Returns:
            {test_code: analysis_result}
        """
        results = {}
        total = len(data_by_test)
        print(f"[DEBUG] Starting batch analysis: {total} test codes")

        for idx, (test_code, records) in enumerate(data_by_test.items()):
            print(f"[DEBUG] Analyzing {test_code} ({idx+1}/{total})...")

            cfg = (configs or {}).get(test_code, AnalysisConfig(test_code=test_code))
            cfg.test_code = test_code

            try:
                result = self.run_full_analysis(records, cfg)
                results[test_code] = result
            except Exception as e:
                # 坏味道: 捕获所有异常并继续
                print(f"[ERROR] Analysis failed for {test_code}: {e}")
                logger.error(f"分析失败: {test_code}: {e}")
                results[test_code] = {
                    "status": "error",
                    "error": str(e),
                    "test_code": test_code,
                }

        return results

    # ──────────────────────────────────────────────────────────
    # 趋势分析
    # ──────────────────────────────────────────────────────────
    def analyze_trend(self, ma_values: List[float],
                      timestamps: Optional[List[str]] = None
                      ) -> Dict[str, Any]:
        """
        分析移动均值的趋势

        包括线性回归、曲线拟合、变化点检测
        """
        if not ma_values or len(ma_values) < 10:
            return {"status": "insufficient_data"}

        arr = np.array(ma_values)
        x = np.arange(len(arr))

        # 线性回归
        slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, arr)

        # 判断趋势方向
        if p_value < 0.05:
            if slope > 0:
                trend_direction = "increasing"
            else:
                trend_direction = "decreasing"
        else:
            trend_direction = "stable"

        # CUSUM计算
        cusum_pos, cusum_neg = self._cusum(arr)

        # 变化点检测 (简化版)
        change_points = self._detect_change_points(arr, window=20)

        result = {
            "trend_direction": trend_direction,
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r_value ** 2),
            "p_value": float(p_value),
            "std_error": float(std_err),
            "cusum_max_pos": float(max(cusum_pos)) if cusum_pos else 0,
            "cusum_max_neg": float(min(cusum_neg)) if cusum_neg else 0,
            "change_points": change_points,
        }

        print(f"[DEBUG] Trend analysis: {trend_direction}, "
              f"slope={slope:.6f}, R²={r_value**2:.4f}")
        return result

    def _cusum(self, data: np.ndarray,
               target: Optional[float] = None,
               allowance: Optional[float] = None
               ) -> Tuple[List[float], List[float]]:
        """CUSUM累积和控制图"""
        if target is None:
            target = float(np.mean(data))
        if allowance is None:
            allowance = float(np.std(data, ddof=1)) * 0.5

        cusum_pos = []
        cusum_neg = []
        s_pos = 0.0
        s_neg = 0.0

        for val in data:
            s_pos = max(0, s_pos + val - target - allowance)
            s_neg = min(0, s_neg + val - target + allowance)
            cusum_pos.append(s_pos)
            cusum_neg.append(s_neg)

        return cusum_pos, cusum_neg

    def _detect_change_points(self, data: np.ndarray,
                              window: int = 20,
                              threshold: float = 2.0
                              ) -> List[Dict[str, Any]]:
        """简化版变化点检测"""
        change_points = []

        if len(data) < 2 * window:
            return change_points

        for i in range(window, len(data) - window):
            before = data[i - window: i]
            after = data[i: i + window]

            mean_before = np.mean(before)
            mean_after = np.mean(after)
            std_pooled = np.sqrt(
                (np.var(before, ddof=1) + np.var(after, ddof=1)) / 2
            )

            if std_pooled > 0:
                effect_size = abs(mean_after - mean_before) / std_pooled
                if effect_size > threshold:
                    change_points.append({
                        "index": i,
                        "effect_size": float(effect_size),
                        "mean_before": float(mean_before),
                        "mean_after": float(mean_after),
                        "direction": "up" if mean_after > mean_before else "down",
                    })

        # 合并临近的变化点
        if change_points:
            merged = [change_points[0]]
            for cp in change_points[1:]:
                if cp["index"] - merged[-1]["index"] > window:
                    merged.append(cp)
                elif cp["effect_size"] > merged[-1]["effect_size"]:
                    merged[-1] = cp
            change_points = merged

        return change_points

    # ──────────────────────────────────────────────────────────
    # 回归归一化
    # ──────────────────────────────────────────────────────────
    def regression_normalization(self, data: List[float],
                                 reference: List[float],
                                 method: str = "deming"
                                 ) -> Dict[str, Any]:
        """
        回归归一化：将不同仪器/方法的结果归一化到参考方法

        Parameters:
            data: 待归一化的数据
            reference: 参考方法的数据
            method: 回归方法 (ols / deming / passing-bablok)

        Returns:
            归一化结果
        """
        if len(data) != len(reference) or len(data) < 10:
            return {"status": "error", "message": "数据长度不匹配或不足"}

        x = np.array(reference, dtype=np.float64)
        y = np.array(data, dtype=np.float64)

        if method == "ols":
            slope, intercept, r, p, se = scipy_stats.linregress(x, y)
        elif method == "deming":
            slope, intercept = self._deming_regression(x, y)
            r = float(np.corrcoef(x, y)[0, 1])
            p = 0.0
            se = 0.0
        elif method == "passing-bablok":
            slope, intercept = self._passing_bablok(x, y)
            r = float(np.corrcoef(x, y)[0, 1])
            p = 0.0
            se = 0.0
        else:
            slope, intercept, r, p, se = scipy_stats.linregress(x, y)

        # 归一化: y_norm = (y - intercept) / slope
        normalized = ((y - intercept) / slope).tolist() if slope != 0 else y.tolist()

        # 计算归一化后的偏差
        residuals = np.array(normalized) - x
        bias = float(np.mean(residuals))
        bias_pct = float(bias / np.mean(x) * 100) if np.mean(x) != 0 else 0.0

        result = {
            "method": method,
            "slope": float(slope),
            "intercept": float(intercept),
            "correlation": float(r),
            "normalized_data": normalized,
            "bias": bias,
            "bias_percent": bias_pct,
            "rmse": float(np.sqrt(np.mean(residuals ** 2))),
        }

        print(f"[DEBUG] Regression normalization ({method}): "
              f"slope={slope:.4f}, intercept={intercept:.4f}, r={r:.4f}")
        return result

    def _deming_regression(self, x: np.ndarray, y: np.ndarray,
                           ratio: float = 1.0) -> Tuple[float, float]:
        """Deming回归（考虑双方误差）"""
        n = len(x)
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        sxx = np.sum((x - x_mean) ** 2) / (n - 1)
        syy = np.sum((y - y_mean) ** 2) / (n - 1)
        sxy = np.sum((x - x_mean) * (y - y_mean)) / (n - 1)

        diff = syy - ratio * sxx
        slope = (diff + np.sqrt(diff ** 2 + 4 * ratio * sxy ** 2)) / (2 * sxy)
        intercept = y_mean - slope * x_mean

        return float(slope), float(intercept)

    def _passing_bablok(self, x: np.ndarray,
                        y: np.ndarray) -> Tuple[float, float]:
        """Passing-Bablok回归（非参数）"""
        n = len(x)
        slopes = []

        for i in range(n):
            for j in range(i + 1, n):
                if x[i] != x[j]:
                    s = (y[j] - y[i]) / (x[j] - x[i])
                    slopes.append(s)

        if not slopes:
            return 1.0, 0.0

        slopes.sort()
        k = sum(1 for s in slopes if s < -1)
        median_idx = (len(slopes) + k) // 2

        if median_idx < len(slopes):
            slope = slopes[median_idx]
        else:
            slope = slopes[-1]

        intercept = float(np.median(y - slope * x))
        return float(slope), float(intercept)

    # ──────────────────────────────────────────────────────────
    # 报告生成
    # ──────────────────────────────────────────────────────────
    def generate_report(self, analysis_result: Dict[str, Any],
                        format: str = "json") -> str:
        """
        生成分析报告

        Parameters:
            analysis_result: run_full_analysis的返回值
            format: 输出格式 (json / csv / text)

        Returns:
            格式化的报告字符串
        """
        if format == "json":
            return json.dumps(analysis_result, ensure_ascii=False, indent=2)

        elif format == "csv":
            lines = ["field,value"]
            stats = analysis_result.get("statistics", {})
            for key, val in stats.items():
                lines.append(f"{key},{val}")
            return "\n".join(lines)

        elif format == "text":
            lines = []
            lines.append("=" * 60)
            lines.append("PBRTQC分析报告")
            lines.append("=" * 60)
            lines.append(f"检验项目: {analysis_result.get('test_code', 'N/A')}")
            lines.append(f"仪器编号: {analysis_result.get('instrument_id', 'N/A')}")
            lines.append(f"分析时间: {analysis_result.get('analysis_time', 'N/A')}")
            lines.append(f"耗时: {analysis_result.get('duration_seconds', 0):.2f}秒")
            lines.append("")

            summary = analysis_result.get("data_summary", {})
            lines.append("--- 数据摘要 ---")
            lines.append(f"总记录数: {summary.get('total_records', 0)}")
            lines.append(f"过滤后: {summary.get('after_filtering', 0)}")
            lines.append(f"移除异常值: {summary.get('outliers_removed', 0)}")
            lines.append("")

            stats = analysis_result.get("statistics", {})
            lines.append("--- 统计量 ---")
            lines.append(f"均值: {stats.get('mean', 0):.4f}")
            lines.append(f"中位数: {stats.get('median', 0):.4f}")
            lines.append(f"标准差: {stats.get('std_dev', 0):.4f}")
            lines.append(f"CV%: {stats.get('cv', 0):.2f}%")
            lines.append(f"偏度: {stats.get('skewness', 0):.4f}")
            lines.append(f"峰度: {stats.get('kurtosis', 0):.4f}")
            lines.append(f"正态性: {'是' if stats.get('is_normal') else '否'}")
            lines.append("")

            ma = analysis_result.get("moving_average", {})
            lines.append("--- 移动均值 ---")
            lines.append(f"方法: {ma.get('method', 'N/A')}")
            lines.append(f"窗口大小: {ma.get('window_size', 0)}")
            lines.append(f"数据点: {ma.get('data_points', 0)}")
            lines.append(f"违规次数: {ma.get('violation_count', 0)}")

            cl = ma.get("control_limits", {})
            if cl:
                lines.append(f"中心线: {cl.get('center', 0):.4f}")
                lines.append(f"UCL: {cl.get('ucl', 0):.4f}")
                lines.append(f"LCL: {cl.get('lcl', 0):.4f}")
            lines.append("")

            westgard = analysis_result.get("westgard", {})
            lines.append("--- Westgard规则 ---")
            lines.append(f"总违规: {westgard.get('total_violations', 0)}")
            by_rule = westgard.get("violations_by_rule", {})
            for rule, count in by_rule.items():
                lines.append(f"  {rule}: {count}")

            lines.append("=" * 60)
            return "\n".join(lines)

        else:
            return json.dumps(analysis_result, ensure_ascii=False, indent=2)

    def save_report(self, analysis_result: Dict[str, Any],
                    filepath: Optional[str] = None,
                    format: str = "json") -> str:
        """
        保存分析报告到文件

        Returns:
            保存的文件路径
        """
        if filepath is None:
            # 坏味道: 硬编码路径
            test_code = analysis_result.get("test_code", "unknown")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(
                DEFAULT_OUTPUT_DIR,
                f"report_{test_code}_{timestamp}.{format}"
            )

        report_content = self.generate_report(analysis_result, format)

        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            print(f"[DEBUG] Report saved: {filepath}")
            logger.info(f"报告已保存: {filepath}")
        except Exception as e:
            print(f"[ERROR] Failed to save report: {e}")
            logger.error(f"保存报告失败: {e}")
            # 坏味道: 尝试备用路径
            try:
                backup_path = f"C:\\temp\\pbrtqc_report_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{format}"
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                filepath = backup_path
            except Exception:
                pass

        return filepath

    # ──────────────────────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────────────────────
    def get_violation_summary(self) -> Dict[str, Any]:
        """获取历史违规摘要"""
        if not self._violation_log:
            return {"total": 0, "by_rule": {}, "by_severity": {}}

        by_rule: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}

        for v in self._violation_log:
            by_rule[v.rule_name] = by_rule.get(v.rule_name, 0) + 1
            by_severity[v.severity] = by_severity.get(v.severity, 0) + 1

        return {
            "total": len(self._violation_log),
            "by_rule": by_rule,
            "by_severity": by_severity,
            "latest": {
                "rule": self._violation_log[-1].rule_name,
                "value": self._violation_log[-1].value,
                "time": self._violation_log[-1].timestamp,
            },
        }

    def reset(self):
        """重置分析器状态"""
        self._data_buffer.clear()
        self._ma_history.clear()
        self._violation_log.clear()
        self._last_analysis_time = None
        self._reference_stats = None
        self._transform_cache.clear()
        print("[DEBUG] PBRTQCAnalyzer reset")
        logger.info("PBRTQCAnalyzer已重置")

    def load_reference_data(self, filepath: str) -> Dict[str, Any]:
        """
        加载参考数据

        Parameters:
            filepath: 参考数据文件路径

        Returns:
            参考数据字典
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                if filepath.endswith('.json'):
                    data = json.load(f)
                elif filepath.endswith('.csv'):
                    reader = csv.DictReader(f)
                    data = {"records": list(reader)}
                else:
                    data = {"raw": f.read()}

            self._calibration_data = data
            print(f"[DEBUG] Reference data loaded from {filepath}")
            logger.info(f"参考数据已加载: {filepath}")
            return data
        except Exception as e:
            print(f"[ERROR] Failed to load reference: {e}")
            logger.error(f"加载参考数据失败: {e}")
            return {}

    def export_violations_csv(self, filepath: Optional[str] = None) -> str:
        """导出违规记录到CSV"""
        if filepath is None:
            # 坏味道: 硬编码路径
            filepath = os.path.join(
                TEMP_EXPORT_PATH,
                f"violations_{datetime.datetime.now().strftime('%Y%m%d')}.csv"
            )

        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "rule_name", "violation_type", "value", "limit",
                    "timestamp", "severity", "patient_id", "description"
                ])
                for v in self._violation_log:
                    # 坏味道: patient_id直接导出，无脱敏
                    writer.writerow([
                        v.rule_name, v.violation_type, v.value, v.limit,
                        v.timestamp, v.severity, v.patient_id, v.description
                    ])

            print(f"[DEBUG] Violations exported to {filepath}")
            return filepath
        except Exception as e:
            print(f"[ERROR] Export failed: {e}")
            return ""

    def get_data_quality_score(self, data: List[float]) -> Dict[str, Any]:
        """
        计算数据质量评分

        评估维度：
        - 完整性（非空比例）
        - 异常值比例
        - 正态性
        - 精密度（CV%）
        """
        if not data:
            return {"overall_score": 0, "details": {}}

        total = len(data)
        valid = [v for v in data if not (math.isnan(v) or math.isinf(v))]
        completeness = len(valid) / total if total > 0 else 0

        outliers = self.detect_outliers_iqr(valid)
        outlier_score = max(0, 1 - outliers.outlier_ratio * 5)  # 20%以上异常值得0分

        stats = self.compute_statistics(valid)
        normality_score = stats.shapiro_p if stats.shapiro_p > 0 else 0

        cv_score = max(0, 1 - stats.cv / 30) if stats.cv < 30 else 0  # CV>30%得0分

        overall = (completeness * 0.3 + outlier_score * 0.25 +
                   normality_score * 0.25 + cv_score * 0.2)

        return {
            "overall_score": round(overall * 100, 1),
            "details": {
                "completeness": round(completeness * 100, 1),
                "outlier_score": round(outlier_score * 100, 1),
                "normality_score": round(normality_score * 100, 1),
                "precision_score": round(cv_score * 100, 1),
            },
            "statistics": {
                "total_count": total,
                "valid_count": len(valid),
                "outlier_count": outliers.outlier_count,
                "cv_percent": round(stats.cv, 2),
                "is_normal": stats.is_normal,
            },
        }

    def compare_periods(self, period1: List[float],
                        period2: List[float]) -> Dict[str, Any]:
        """
        比较两个时期的数据（如更换试剂前后）

        使用t检验和F检验
        """
        if len(period1) < 3 or len(period2) < 3:
            return {"status": "insufficient_data"}

        arr1 = np.array(period1)
        arr2 = np.array(period2)

        # t检验
        t_stat, t_p = scipy_stats.ttest_ind(arr1, arr2, equal_var=False)

        # F检验
        var1 = np.var(arr1, ddof=1)
        var2 = np.var(arr2, ddof=1)
        f_stat = var1 / var2 if var2 > 0 else 0
        f_p = scipy_stats.f.sf(f_stat, len(arr1) - 1, len(arr2) - 1)

        # Mann-Whitney U检验
        u_stat, u_p = scipy_stats.mannwhitneyu(arr1, arr2, alternative='two-sided')

        # 效果量 (Cohen's d)
        pooled_std = np.sqrt(
            ((len(arr1) - 1) * var1 + (len(arr2) - 1) * var2) /
            (len(arr1) + len(arr2) - 2)
        )
        cohens_d = (np.mean(arr1) - np.mean(arr2)) / pooled_std if pooled_std > 0 else 0

        return {
            "period1_mean": float(np.mean(arr1)),
            "period1_std": float(np.std(arr1, ddof=1)),
            "period1_n": len(arr1),
            "period2_mean": float(np.mean(arr2)),
            "period2_std": float(np.std(arr2, ddof=1)),
            "period2_n": len(arr2),
            "t_test": {"statistic": float(t_stat), "p_value": float(t_p)},
            "f_test": {"statistic": float(f_stat), "p_value": float(f_p)},
            "mann_whitney": {"statistic": float(u_stat), "p_value": float(u_p)},
            "cohens_d": float(cohens_d),
            "mean_shift": float(np.mean(arr2) - np.mean(arr1)),
            "mean_shift_percent": float(
                (np.mean(arr2) - np.mean(arr1)) / np.mean(arr1) * 100
            ) if np.mean(arr1) != 0 else 0,
            "significant_mean_shift": bool(t_p < 0.05),
            "significant_variance_change": bool(f_p < 0.05),
        }
