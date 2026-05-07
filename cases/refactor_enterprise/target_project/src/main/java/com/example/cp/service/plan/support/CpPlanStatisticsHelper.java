package com.example.cp.service.plan.support;

import com.example.cp.enums.plan.NormalTransAlgorithmEnum;
import org.springframework.util.CollectionUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 临床路径统计计算工具类
 * <p>
 * 提供移动平均、均值、标准差、开方、正态转换等纯统计计算。
 * 无状态、无依赖，仅做数值计算。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-15
 */
public final class CpPlanStatisticsHelper {

    private CpPlanStatisticsHelper() {
        // 工具类禁止实例化
    }

    /**
     * 计算移动平均值
     */
    public static List<BigDecimal> calculateMovingAverage(List<BigDecimal> values, int window) {
        if (values == null || values.size() < window) {
            return values != null ? values : Collections.emptyList();
        }

        List<BigDecimal> movingAvgs = new ArrayList<>();
        for (int i = 0; i <= values.size() - window; i++) {
            BigDecimal sum = BigDecimal.ZERO;
            for (int j = i; j < i + window; j++) {
                sum = sum.add(values.get(j));
            }
            BigDecimal avg = sum.divide(new BigDecimal(window), 6, RoundingMode.HALF_UP);
            movingAvgs.add(avg);
        }
        return movingAvgs;
    }

    /**
     * 计算均值
     */
    public static BigDecimal calculateMean(List<BigDecimal> values) {
        if (CollectionUtils.isEmpty(values)) {
            return BigDecimal.ZERO;
        }
        BigDecimal sum = values.stream().reduce(BigDecimal.ZERO, BigDecimal::add);
        return sum.divide(new BigDecimal(values.size()), 6, RoundingMode.HALF_UP);
    }

    /**
     * 计算标准差
     */
    public static BigDecimal calculateStandardDeviation(List<BigDecimal> values, BigDecimal mean) {
        if (CollectionUtils.isEmpty(values) || values.size() < 2) {
            return BigDecimal.ZERO;
        }

        BigDecimal sumOfSquares = BigDecimal.ZERO;
        for (BigDecimal value : values) {
            BigDecimal diff = value.subtract(mean);
            sumOfSquares = sumOfSquares.add(diff.multiply(diff));
        }

        BigDecimal variance = sumOfSquares.divide(
                new BigDecimal(values.size() - 1), 10, RoundingMode.HALF_UP);

        return sqrt(variance, 6);
    }

    /**
     * BigDecimal开方（牛顿迭代法）
     */
    public static BigDecimal sqrt(BigDecimal value, int scale) {
        if (value.compareTo(BigDecimal.ZERO) <= 0) {
            return BigDecimal.ZERO;
        }

        BigDecimal two = new BigDecimal("2");
        BigDecimal x0 = new BigDecimal(Math.sqrt(value.doubleValue()));
        BigDecimal x1;

        for (int i = 0; i < 20; i++) {
            x1 = value.divide(x0, scale + 2, RoundingMode.HALF_UP);
            x1 = x1.add(x0);
            x1 = x1.divide(two, scale + 2, RoundingMode.HALF_UP);
            if (x0.compareTo(x1) == 0) break;
            x0 = x1;
        }

        return x0.setScale(scale, RoundingMode.HALF_UP);
    }

    /**
     * 应用正态转换
     */
    public static List<BigDecimal> applyNormalTransform(List<BigDecimal> values, String transCode) {
        NormalTransAlgorithmEnum transAlgo = NormalTransAlgorithmEnum.fromCode(transCode);
        if (transAlgo == null) {
            return values;
        }

        switch (transAlgo) {
            case LOG_TRANSFORM:
                return values.stream()
                        .map(v -> {
                            if (v.compareTo(BigDecimal.ZERO) <= 0) return v;
                            return new BigDecimal(Math.log(v.doubleValue()))
                                    .setScale(6, RoundingMode.HALF_UP);
                        })
                        .collect(Collectors.toList());

            case SQRT_TRANSFORM:
                return values.stream()
                        .map(v -> {
                            if (v.compareTo(BigDecimal.ZERO) < 0) return v;
                            return new BigDecimal(Math.sqrt(v.doubleValue()))
                                    .setScale(6, RoundingMode.HALF_UP);
                        })
                        .collect(Collectors.toList());

            case BOX_COX:
                return values.stream()
                        .map(v -> {
                            if (v.compareTo(BigDecimal.ZERO) <= 0) return v;
                            double lambda = 0.5;
                            double transformed = (Math.pow(v.doubleValue(), lambda) - 1) / lambda;
                            return new BigDecimal(transformed).setScale(6, RoundingMode.HALF_UP);
                        })
                        .collect(Collectors.toList());

            default:
                return values;
        }
    }

    /**
     * 应用Westgard临床路径规则
     */
    public static List<Map<String, Object>> applyWestgardRules(
            List<BigDecimal> values, BigDecimal mean, BigDecimal sd) {

        List<Map<String, Object>> violations = new ArrayList<>();
        if (CollectionUtils.isEmpty(values) || sd.compareTo(BigDecimal.ZERO) == 0) {
            return violations;
        }

        BigDecimal twoSd = sd.multiply(new BigDecimal("2"));
        BigDecimal threeSd = sd.multiply(new BigDecimal("3"));

        for (int i = 0; i < values.size(); i++) {
            BigDecimal value = values.get(i);
            BigDecimal deviation = value.subtract(mean).abs();

            // 1-3s规则：单个值超过±3SD
            if (deviation.compareTo(threeSd) > 0) {
                Map<String, Object> v = new java.util.LinkedHashMap<>();
                v.put("ruleCode", "1-3s");
                v.put("ruleName", "单值超过3个标准差");
                v.put("index", i);
                v.put("value", value);
                v.put("deviation", deviation);
                v.put("level", "CRITICAL");
                violations.add(v);
            }

            // 1-2s规则：单个值超过±2SD（警告）
            if (deviation.compareTo(twoSd) > 0 && deviation.compareTo(threeSd) <= 0) {
                Map<String, Object> v = new java.util.LinkedHashMap<>();
                v.put("ruleCode", "1-2s");
                v.put("ruleName", "单值超过2个标准差");
                v.put("index", i);
                v.put("value", value);
                v.put("deviation", deviation);
                v.put("level", "WARNING");
                violations.add(v);
            }

            // 2-2s规则：连续2个值超过同侧±2SD
            if (i > 0) {
                BigDecimal prevValue = values.get(i - 1);
                BigDecimal prevDev = prevValue.subtract(mean);
                BigDecimal currDev = value.subtract(mean);

                if (prevDev.abs().compareTo(twoSd) > 0 && currDev.abs().compareTo(twoSd) > 0
                        && prevDev.signum() == currDev.signum()) {
                    Map<String, Object> v = new java.util.LinkedHashMap<>();
                    v.put("ruleCode", "2-2s");
                    v.put("ruleName", "连续2值同侧超过2个标准差");
                    v.put("index", i);
                    v.put("value", value);
                    v.put("level", "ERROR");
                    violations.add(v);
                }
            }

            // R-4s规则：连续2个值之差超过4SD
            if (i > 0) {
                BigDecimal prevValue = values.get(i - 1);
                BigDecimal range = value.subtract(prevValue).abs();
                BigDecimal fourSd = sd.multiply(new BigDecimal("4"));
                if (range.compareTo(fourSd) > 0) {
                    Map<String, Object> v = new java.util.LinkedHashMap<>();
                    v.put("ruleCode", "R-4s");
                    v.put("ruleName", "连续2值之差超过4个标准差");
                    v.put("index", i);
                    v.put("value", value);
                    v.put("level", "ERROR");
                    violations.add(v);
                }
            }

            // 10x规则：连续10个值在均值同侧
            if (i >= 9) {
                boolean allSameSide = true;
                int firstSign = values.get(i - 9).subtract(mean).signum();
                if (firstSign == 0) firstSign = 1;
                for (int k = i - 8; k <= i; k++) {
                    int sign = values.get(k).subtract(mean).signum();
                    if (sign == 0) sign = 1;
                    if (sign != firstSign) {
                        allSameSide = false;
                        break;
                    }
                }
                if (allSameSide) {
                    Map<String, Object> v = new java.util.LinkedHashMap<>();
                    v.put("ruleCode", "10x");
                    v.put("ruleName", "连续10值在均值同侧");
                    v.put("index", i);
                    v.put("value", value);
                    v.put("level", "WARNING");
                    violations.add(v);
                }
            }
        }

        return violations;
    }
}
