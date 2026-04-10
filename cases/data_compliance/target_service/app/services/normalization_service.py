"""
回归归一化服务
用于不同仪器/方法间的结果归一化和可比性评估
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


class NormalizationService:
    """
    回归归一化服务

    支持方法:
    - OLS (Ordinary Least Squares)
    - Deming回归
    - Passing-Bablok回归
    - 加权Deming回归
    """

    def __init__(self):
        self._normalization_cache: Dict[str, Dict[str, Any]] = {}
        self._comparison_history: List[Dict[str, Any]] = []
        print("[DEBUG] NormalizationService initialized")
        logger.info("NormalizationService初始化完成")

    def normalize(self, source_data: List[float],
                  reference_data: List[float],
                  method: str = "deming") -> Dict[str, Any]:
        """
        执行回归归一化

        Parameters:
            source_data: 源仪器/方法的数据
            reference_data: 参考仪器/方法的数据
            method: 回归方法

        Returns:
            归一化结果字典
        """
        if len(source_data) != len(reference_data):
            return {"status": "error",
                    "message": "数据长度不匹配"}

        if len(source_data) < 10:
            return {"status": "error",
                    "message": f"数据量不足: {len(source_data)} < 10"}

        x = np.array(reference_data, dtype=np.float64)
        y = np.array(source_data, dtype=np.float64)

        # 移除含NaN的配对
        mask = ~(np.isnan(x) | np.isnan(y))
        x = x[mask]
        y = y[mask]

        if len(x) < 10:
            return {"status": "error", "message": "有效配对不足"}

        # 执行回归
        if method == "ols":
            slope, intercept, r, p, se = scipy_stats.linregress(x, y)
        elif method == "deming":
            slope, intercept = self._deming_regression(x, y)
            r = float(np.corrcoef(x, y)[0, 1])
            p, se = 0.0, 0.0
        elif method == "passing-bablok":
            slope, intercept = self._passing_bablok_regression(x, y)
            r = float(np.corrcoef(x, y)[0, 1])
            p, se = 0.0, 0.0
        elif method == "weighted-deming":
            slope, intercept = self._weighted_deming(x, y)
            r = float(np.corrcoef(x, y)[0, 1])
            p, se = 0.0, 0.0
        else:
            slope, intercept, r, p, se = scipy_stats.linregress(x, y)

        # 归一化
        if slope != 0:
            normalized = ((y - intercept) / slope).tolist()
        else:
            normalized = y.tolist()

        # 统计
        residuals = np.array(normalized) - x
        bias = float(np.mean(residuals))
        bias_pct = float(bias / np.mean(x) * 100) if np.mean(x) != 0 else 0
        rmse = float(np.sqrt(np.mean(residuals ** 2)))

        # Bland-Altman分析
        bland_altman = self._bland_altman(x, np.array(normalized))

        result = {
            "status": "success",
            "method": method,
            "sample_count": int(len(x)),
            "regression": {
                "slope": float(slope),
                "intercept": float(intercept),
                "correlation": float(r),
                "r_squared": float(r ** 2),
            },
            "performance": {
                "bias": bias,
                "bias_percent": bias_pct,
                "rmse": rmse,
                "se": float(se) if se else 0,
            },
            "bland_altman": bland_altman,
            "normalized_data": normalized,
        }

        print(f"[DEBUG] Normalization ({method}): slope={slope:.4f}, "
              f"intercept={intercept:.4f}, r={r:.4f}")
        logger.info(f"归一化完成: {method}, r={r:.4f}, bias={bias:.4f}")
        return result

    def _deming_regression(self, x: np.ndarray, y: np.ndarray,
                           error_ratio: float = 1.0
                           ) -> Tuple[float, float]:
        """Deming回归"""
        n = len(x)
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        sxx = np.sum((x - x_mean) ** 2) / (n - 1)
        syy = np.sum((y - y_mean) ** 2) / (n - 1)
        sxy = np.sum((x - x_mean) * (y - y_mean)) / (n - 1)

        diff = syy - error_ratio * sxx
        discriminant = diff ** 2 + 4 * error_ratio * sxy ** 2

        if discriminant < 0:
            # 退化为OLS
            slope, intercept, _, _, _ = scipy_stats.linregress(x, y)
            return float(slope), float(intercept)

        slope = (diff + np.sqrt(discriminant)) / (2 * sxy)
        intercept = y_mean - slope * x_mean

        return float(slope), float(intercept)

    def _passing_bablok_regression(self, x: np.ndarray,
                                    y: np.ndarray
                                    ) -> Tuple[float, float]:
        """Passing-Bablok非参数回归"""
        n = len(x)
        slopes = []

        for i in range(n):
            for j in range(i + 1, n):
                dx = x[j] - x[i]
                dy = y[j] - y[i]
                if dx != 0:
                    slopes.append(dy / dx)

        if not slopes:
            return 1.0, 0.0

        slopes.sort()

        # 修正偏移
        k = sum(1 for s in slopes if s < -1)

        # 中位数斜率
        m = len(slopes)
        idx = (m + k) // 2
        if idx >= m:
            idx = m - 1

        if (m + k) % 2 == 0 and idx > 0:
            slope = (slopes[idx - 1] + slopes[idx]) / 2
        else:
            slope = slopes[idx]

        intercept = float(np.median(y - slope * x))
        return float(slope), float(intercept)

    def _weighted_deming(self, x: np.ndarray, y: np.ndarray,
                         error_ratio: float = 1.0
                         ) -> Tuple[float, float]:
        """加权Deming回归（权重与值成反比）"""
        weights = 1.0 / (np.abs(x) + np.abs(y) + 1e-10)
        weights = weights / np.sum(weights) * len(weights)

        x_mean = np.average(x, weights=weights)
        y_mean = np.average(y, weights=weights)

        sxx = np.sum(weights * (x - x_mean) ** 2) / (np.sum(weights) - 1)
        syy = np.sum(weights * (y - y_mean) ** 2) / (np.sum(weights) - 1)
        sxy = np.sum(weights * (x - x_mean) * (y - y_mean)) / (np.sum(weights) - 1)

        diff = syy - error_ratio * sxx
        discriminant = diff ** 2 + 4 * error_ratio * sxy ** 2

        if discriminant < 0 or sxy == 0:
            return 1.0, float(y_mean - x_mean)

        slope = (diff + np.sqrt(discriminant)) / (2 * sxy)
        intercept = y_mean - slope * x_mean

        return float(slope), float(intercept)

    def _bland_altman(self, x: np.ndarray,
                      y: np.ndarray) -> Dict[str, float]:
        """Bland-Altman一致性分析"""
        mean_vals = (x + y) / 2
        diff_vals = y - x

        mean_diff = float(np.mean(diff_vals))
        std_diff = float(np.std(diff_vals, ddof=1))

        return {
            "mean_difference": mean_diff,
            "std_difference": std_diff,
            "upper_limit": mean_diff + 1.96 * std_diff,
            "lower_limit": mean_diff - 1.96 * std_diff,
            "within_limits_pct": float(
                np.mean(
                    (diff_vals >= mean_diff - 1.96 * std_diff) &
                    (diff_vals <= mean_diff + 1.96 * std_diff)
                ) * 100
            ),
        }

    def compare_instruments(self, instrument1_data: List[float],
                            instrument2_data: List[float],
                            test_code: str = "",
                            method: str = "deming"
                            ) -> Dict[str, Any]:
        """
        比较两台仪器的检测结果

        Returns:
            包含回归分析和统计检验的比较结果
        """
        result = self.normalize(instrument1_data, instrument2_data, method)

        if result.get("status") != "success":
            return result

        arr1 = np.array(instrument1_data)
        arr2 = np.array(instrument2_data)

        # t检验
        t_stat, t_p = scipy_stats.ttest_rel(arr1, arr2)

        # Wilcoxon符号秩检验
        try:
            w_stat, w_p = scipy_stats.wilcoxon(arr1, arr2)
        except Exception:
            w_stat, w_p = 0.0, 1.0

        # Cohen's d
        diff = arr1 - arr2
        cohens_d = float(np.mean(diff) / np.std(diff, ddof=1)) if np.std(diff, ddof=1) > 0 else 0

        result["comparison"] = {
            "test_code": test_code,
            "paired_t_test": {
                "statistic": float(t_stat),
                "p_value": float(t_p),
                "significant": bool(t_p < 0.05),
            },
            "wilcoxon_test": {
                "statistic": float(w_stat),
                "p_value": float(w_p),
                "significant": bool(w_p < 0.05),
            },
            "cohens_d": cohens_d,
            "clinically_significant": abs(cohens_d) > 0.5,
        }

        self._comparison_history.append({
            "test_code": test_code,
            "method": method,
            "r": result["regression"]["correlation"],
            "bias_pct": result["performance"]["bias_percent"],
        })

        return result

    def batch_normalize(self, data_pairs: Dict[str, Tuple[List[float], List[float]]],
                        method: str = "deming"
                        ) -> Dict[str, Dict[str, Any]]:
        """
        批量归一化多个检验项目

        Parameters:
            data_pairs: {test_code: (source_data, reference_data)}

        Returns:
            {test_code: normalization_result}
        """
        results = {}
        for test_code, (source, reference) in data_pairs.items():
            print(f"[DEBUG] Normalizing {test_code}...")
            try:
                result = self.normalize(source, reference, method)
                results[test_code] = result
            except Exception as e:
                print(f"[ERROR] Normalization failed for {test_code}: {e}")
                results[test_code] = {"status": "error", "message": str(e)}

        return results

    def evaluate_sigma(self, bias_pct: float, cv_pct: float,
                       tea_pct: float) -> Dict[str, Any]:
        """
        评估Sigma水平

        Sigma = (TEa - |Bias|) / CV

        Parameters:
            bias_pct: 偏倚百分比
            cv_pct: 变异系数百分比
            tea_pct: 总允许误差百分比

        Returns:
            Sigma评估结果
        """
        if cv_pct == 0:
            sigma = 0
        else:
            sigma = (tea_pct - abs(bias_pct)) / cv_pct

        # 质量等级
        if sigma >= 6:
            quality = "世界级"
        elif sigma >= 5:
            quality = "优秀"
        elif sigma >= 4:
            quality = "良好"
        elif sigma >= 3:
            quality = "可接受"
        elif sigma >= 2:
            quality = "边缘"
        else:
            quality = "不可接受"

        # 建议的QC策略
        if sigma >= 5:
            qc_strategy = "使用1-3s规则，单水平QC"
        elif sigma >= 4:
            qc_strategy = "使用1-3s/2-2s规则，双水平QC"
        elif sigma >= 3:
            qc_strategy = "使用多规则（1-3s/2-2s/R-4s），双水平QC，增加QC频率"
        else:
            qc_strategy = "需要改善方法性能，当前QC无法保证质量"

        result = {
            "sigma": round(sigma, 2),
            "bias_pct": bias_pct,
            "cv_pct": cv_pct,
            "tea_pct": tea_pct,
            "quality_level": quality,
            "qc_strategy": qc_strategy,
        }

        print(f"[DEBUG] Sigma evaluation: {sigma:.2f} ({quality})")
        return result

    def get_comparison_history(self) -> List[Dict[str, Any]]:
        """获取比较历史"""
        return self._comparison_history
