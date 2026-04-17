package com.example.cp.dto.client.request;

import com.example.cp.enums.plan.AlgorithmEnum;
import com.example.cp.enums.plan.NormalTransAlgorithmEnum;
import com.example.cp.enums.plan.TailProcessingEnum;
import com.example.cp.exception.CpBusinessException;
import com.example.cp.exception.CommonErrorCode;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 数据分析请求参数工厂
 * <p>
 * 负责构建发送给第三方数据分析引擎的请求参数。
 * 支持多种分析场景：
 * - 室内临床路径分析（IQC）
 * - 室间质评分析（EQA）
 * - 路径依从率分析
 * - 患者数据分析
 * - 比对分析
 * </p>
 *
 * @author cp-team
 * @since 2024-02-20
 */
@Slf4j
@Component
public class DataAnalysisRequestParamFactory {

    // ========== 硬编码的API端点（坏味道：应该配置化） ==========
    private static final String IQC_ANALYSIS_URL = "http://192.168.1.100:8080/api/analysis/iqc";
    private static final String EQA_ANALYSIS_URL = "http://192.168.1.100:8080/api/analysis/eqa";
    private static final String MOVING_AVG_URL = "http://192.168.1.100:8080/api/analysis/moving-avg";
    private static final String PATIENT_DATA_URL = "http://192.168.1.100:8080/api/analysis/patient";
    private static final String COMPARISON_URL = "http://192.168.1.100:8080/api/analysis/comparison";

    private static final String API_KEY = "cp-analysis-key-2024";
    private static final String API_VERSION = "v2.1";
    private static final int DEFAULT_TIMEOUT = 30000;
    private static final int MAX_DATA_POINTS = 10000;

    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd");
    private static final DateTimeFormatter DATETIME_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    // ====================================================================
    //                   室内临床路径分析参数构建
    // ====================================================================

    /**
     * 构建室内临床路径分析请求参数
     */
    public Map<String, Object> buildIqcAnalysisParams(
            String labCode, String instrumentCode, String itemCode,
            String controlLotNo, Integer controlLevel,
            String algorithmCode, Integer movingWindow,
            BigDecimal targetMean, BigDecimal targetSd,
            LocalDate startDate, LocalDate endDate,
            Map<String, Object> extraParams) {

        log.info("构建IQC分析参数, labCode={}, itemCode={}, algorithm={}", labCode, itemCode, algorithmCode);

        Map<String, Object> params = new LinkedHashMap<>();

        // 基础参数
        params.put("apiUrl", IQC_ANALYSIS_URL);
        params.put("apiKey", API_KEY);
        params.put("apiVersion", API_VERSION);
        params.put("timeout", DEFAULT_TIMEOUT);
        params.put("requestId", UUID.randomUUID().toString());
        params.put("requestTime", LocalDateTime.now().format(DATETIME_FMT));
        params.put("analysisType", "IQC");

        // 实验室参数
        Map<String, Object> labParams = new LinkedHashMap<>();
        labParams.put("labCode", labCode);
        labParams.put("instrumentCode", instrumentCode);
        labParams.put("itemCode", itemCode);
        labParams.put("controlLotNo", controlLotNo);
        labParams.put("controlLevel", controlLevel);
        params.put("labInfo", labParams);

        // 算法参数
        Map<String, Object> algoParams = new LinkedHashMap<>();
        AlgorithmEnum algorithm = AlgorithmEnum.fromCode(algorithmCode);
        if (algorithm == null) {
            throw new CpBusinessException(CommonErrorCode.INVALID_PARAM,
                    "不支持的分析算法: " + algorithmCode);
        }
        algoParams.put("algorithmCode", algorithm.getCode());
        algoParams.put("algorithmName", algorithm.getName());
        algoParams.put("movingWindow", movingWindow != null ? movingWindow : 20);
        algoParams.put("minDataPoints", 10);
        algoParams.put("maxDataPoints", MAX_DATA_POINTS);
        params.put("algorithmConfig", algoParams);

        // 目标值参数
        Map<String, Object> targetParams = new LinkedHashMap<>();
        targetParams.put("targetMean", targetMean != null ? targetMean.toPlainString() : null);
        targetParams.put("targetSd", targetSd != null ? targetSd.toPlainString() : null);
        if (targetMean != null && targetSd != null && targetMean.compareTo(BigDecimal.ZERO) != 0) {
            BigDecimal cv = targetSd.divide(targetMean, 4, RoundingMode.HALF_UP)
                    .multiply(new BigDecimal("100"));
            targetParams.put("targetCv", cv.toPlainString());
        }
        params.put("targetValues", targetParams);

        // 时间范围
        Map<String, Object> dateRange = new LinkedHashMap<>();
        dateRange.put("startDate", startDate != null ? startDate.format(DATE_FMT) : null);
        dateRange.put("endDate", endDate != null ? endDate.format(DATE_FMT) : null);
        params.put("dateRange", dateRange);

        // 临床路径规则配置
        params.put("rules", buildWestgardRuleConfig(algorithmCode));

        // 额外参数
        if (extraParams != null && !extraParams.isEmpty()) {
            params.put("extraParams", extraParams);
        }

        return params;
    }

    // ====================================================================
    //                   室间质评分析参数构建
    // ====================================================================

    /**
     * 构建室间质评分析请求参数
     */
    public Map<String, Object> buildEqaAnalysisParams(
            String labCode, String instrumentCode, List<String> itemCodes,
            String eqaProgramCode, String eqaYear, String eqaBatch,
            List<Map<String, Object>> eqaResults) {

        log.info("构建EQA分析参数, labCode={}, programCode={}, batch={}",
                labCode, eqaProgramCode, eqaBatch);

        Map<String, Object> params = new LinkedHashMap<>();

        // 基础参数
        params.put("apiUrl", EQA_ANALYSIS_URL);
        params.put("apiKey", API_KEY);
        params.put("apiVersion", API_VERSION);
        params.put("timeout", DEFAULT_TIMEOUT);
        params.put("requestId", UUID.randomUUID().toString());
        params.put("requestTime", LocalDateTime.now().format(DATETIME_FMT));
        params.put("analysisType", "EQA");

        // EQA计划信息
        Map<String, Object> eqaInfo = new LinkedHashMap<>();
        eqaInfo.put("programCode", eqaProgramCode);
        eqaInfo.put("year", eqaYear);
        eqaInfo.put("batch", eqaBatch);
        eqaInfo.put("labCode", labCode);
        eqaInfo.put("instrumentCode", instrumentCode);
        params.put("eqaInfo", eqaInfo);

        // 项目列表
        if (!CollectionUtils.isEmpty(itemCodes)) {
            params.put("itemCodes", itemCodes);
            params.put("itemCount", itemCodes.size());
        }

        // 结果数据
        if (!CollectionUtils.isEmpty(eqaResults)) {
            List<Map<String, Object>> formattedResults = new ArrayList<>();
            for (Map<String, Object> result : eqaResults) {
                Map<String, Object> formatted = new LinkedHashMap<>();
                formatted.put("itemCode", result.get("itemCode"));
                formatted.put("reportedValue", result.get("reportedValue"));
                formatted.put("unit", result.get("unit"));
                formatted.put("method", result.get("method"));
                formatted.put("instrumentModel", result.get("instrumentModel"));
                formatted.put("reagentInfo", result.get("reagentInfo"));
                formattedResults.add(formatted);
            }
            params.put("results", formattedResults);
        }

        // 评估标准
        Map<String, Object> evaluationConfig = new LinkedHashMap<>();
        evaluationConfig.put("method", "Z-SCORE");
        evaluationConfig.put("acceptableRange", 2.0);
        evaluationConfig.put("warningRange", 3.0);
        evaluationConfig.put("peerGrouping", true);
        evaluationConfig.put("methodGrouping", true);
        params.put("evaluationConfig", evaluationConfig);

        return params;
    }

    // ====================================================================
    //                   路径依从率分析参数构建
    // ====================================================================

    /**
     * 构建路径依从率分析请求参数
     */
    public Map<String, Object> buildMovingAvgAnalysisParams(
            String labCode, String instrumentCode, String itemCode,
            Integer movingWindow, String normalTransCode,
            String tailProcessing, Boolean excludeWeekend,
            List<BigDecimal> dataPoints,
            LocalDate startDate, LocalDate endDate) {

        log.info("构建路径依从率分析参数, labCode={}, itemCode={}, window={}, dataPoints={}",
                labCode, itemCode, movingWindow, dataPoints != null ? dataPoints.size() : 0);

        Map<String, Object> params = new LinkedHashMap<>();

        // 基础参数
        params.put("apiUrl", MOVING_AVG_URL);
        params.put("apiKey", API_KEY);
        params.put("apiVersion", API_VERSION);
        params.put("timeout", DEFAULT_TIMEOUT * 2);  // 路径依从率计算可能较慢
        params.put("requestId", UUID.randomUUID().toString());
        params.put("requestTime", LocalDateTime.now().format(DATETIME_FMT));
        params.put("analysisType", "MOVING_AVG");

        // 基础信息
        Map<String, Object> baseInfo = new LinkedHashMap<>();
        baseInfo.put("labCode", labCode);
        baseInfo.put("instrumentCode", instrumentCode);
        baseInfo.put("itemCode", itemCode);
        params.put("baseInfo", baseInfo);

        // 路径依从率配置
        Map<String, Object> movingAvgConfig = new LinkedHashMap<>();
        movingAvgConfig.put("windowSize", movingWindow != null ? movingWindow : 20);
        movingAvgConfig.put("minWindowSize", 5);
        movingAvgConfig.put("maxWindowSize", 100);
        movingAvgConfig.put("weightedAverage", false);
        movingAvgConfig.put("exponentialSmoothing", false);
        params.put("movingAvgConfig", movingAvgConfig);

        // 正态转换配置
        if (StringUtils.hasText(normalTransCode)) {
            NormalTransAlgorithmEnum transAlgo = NormalTransAlgorithmEnum.fromCode(normalTransCode);
            if (transAlgo != null) {
                Map<String, Object> normalTransConfig = new LinkedHashMap<>();
                normalTransConfig.put("code", transAlgo.getCode());
                normalTransConfig.put("name", transAlgo.getName());
                normalTransConfig.put("enabled", true);

                // Box-Cox参数
                if ("BOX_COX".equals(normalTransCode)) {
                    normalTransConfig.put("lambda", 0.5);
                    normalTransConfig.put("autoLambda", true);
                }

                params.put("normalTransConfig", normalTransConfig);
            }
        }

        // 尾数处理配置
        if (StringUtils.hasText(tailProcessing)) {
            TailProcessingEnum tailEnum = TailProcessingEnum.fromCode(tailProcessing);
            if (tailEnum != null) {
                Map<String, Object> tailConfig = new LinkedHashMap<>();
                tailConfig.put("code", tailEnum.getCode());
                tailConfig.put("name", tailEnum.getName());
                tailConfig.put("decimalPlaces", tailEnum.getDecimalPlaces());
                tailConfig.put("roundingMode", "HALF_UP");
                params.put("tailProcessingConfig", tailConfig);
            }
        }

        // 数据过滤配置
        Map<String, Object> filterConfig = new LinkedHashMap<>();
        filterConfig.put("excludeWeekend", Boolean.TRUE.equals(excludeWeekend));
        filterConfig.put("excludeHoliday", false);
        filterConfig.put("outlierDetection", true);
        filterConfig.put("outlierMethod", "GRUBBS");
        filterConfig.put("outlierSignificance", 0.05);
        params.put("filterConfig", filterConfig);

        // 时间范围
        Map<String, Object> dateRange = new LinkedHashMap<>();
        dateRange.put("startDate", startDate != null ? startDate.format(DATE_FMT) : null);
        dateRange.put("endDate", endDate != null ? endDate.format(DATE_FMT) : null);
        params.put("dateRange", dateRange);

        // 数据点
        if (!CollectionUtils.isEmpty(dataPoints)) {
            if (dataPoints.size() > MAX_DATA_POINTS) {
                log.warn("数据点数量超过最大限制, 将截断: {} -> {}", dataPoints.size(), MAX_DATA_POINTS);
                dataPoints = dataPoints.subList(0, MAX_DATA_POINTS);
            }
            params.put("dataPoints", dataPoints.stream()
                    .map(BigDecimal::toPlainString)
                    .collect(Collectors.toList()));
            params.put("dataPointCount", dataPoints.size());
        }

        return params;
    }

    // ====================================================================
    //                   患者数据分析参数构建
    // ====================================================================

    /**
     * 构建患者数据分析请求参数
     */
    public Map<String, Object> buildPatientDataAnalysisParams(
            String labCode, String instrumentCode, String itemCode,
            Integer sampleType, String methodCode,
            LocalDate startDate, LocalDate endDate,
            Map<String, Object> patientFilters) {

        log.info("构建患者数据分析参数, labCode={}, itemCode={}, sampleType={}",
                labCode, itemCode, sampleType);

        Map<String, Object> params = new LinkedHashMap<>();

        // 基础参数
        params.put("apiUrl", PATIENT_DATA_URL);
        params.put("apiKey", API_KEY);
        params.put("apiVersion", API_VERSION);
        params.put("timeout", DEFAULT_TIMEOUT * 3);  // 患者数据分析可能较慢
        params.put("requestId", UUID.randomUUID().toString());
        params.put("requestTime", LocalDateTime.now().format(DATETIME_FMT));
        params.put("analysisType", "PATIENT_DATA");

        // 基础信息
        Map<String, Object> baseInfo = new LinkedHashMap<>();
        baseInfo.put("labCode", labCode);
        baseInfo.put("instrumentCode", instrumentCode);
        baseInfo.put("itemCode", itemCode);
        params.put("baseInfo", baseInfo);

        // 样本类型过滤
        Map<String, Object> sampleConfig = new LinkedHashMap<>();
        sampleConfig.put("sampleType", sampleType);
        sampleConfig.put("methodCode", methodCode);
        sampleConfig.put("excludeQcSamples", true);
        sampleConfig.put("excludeRepeatSamples", true);
        sampleConfig.put("excludeAbnormalSamples", false);
        params.put("sampleConfig", sampleConfig);

        // 患者过滤条件
        Map<String, Object> filterConfig = new LinkedHashMap<>();
        if (patientFilters != null) {
            if (patientFilters.containsKey("gender")) {
                filterConfig.put("gender", patientFilters.get("gender"));
            }
            if (patientFilters.containsKey("ageMin")) {
                filterConfig.put("ageMin", patientFilters.get("ageMin"));
            }
            if (patientFilters.containsKey("ageMax")) {
                filterConfig.put("ageMax", patientFilters.get("ageMax"));
            }
            if (patientFilters.containsKey("visitType")) {
                filterConfig.put("visitType", patientFilters.get("visitType"));
            }
            if (patientFilters.containsKey("deptCodes")) {
                filterConfig.put("deptCodes", patientFilters.get("deptCodes"));
            }
        }
        params.put("patientFilter", filterConfig);

        // 统计分析配置
        Map<String, Object> statConfig = new LinkedHashMap<>();
        statConfig.put("calculateMean", true);
        statConfig.put("calculateMedian", true);
        statConfig.put("calculateSd", true);
        statConfig.put("calculatePercentiles", true);
        statConfig.put("percentileValues", Arrays.asList(2.5, 5, 25, 50, 75, 95, 97.5));
        statConfig.put("normalityTest", true);
        statConfig.put("normalityMethod", "SHAPIRO_WILK");
        statConfig.put("histogramBins", 50);
        params.put("statisticsConfig", statConfig);

        // 时间范围
        Map<String, Object> dateRange = new LinkedHashMap<>();
        dateRange.put("startDate", startDate != null ? startDate.format(DATE_FMT) : null);
        dateRange.put("endDate", endDate != null ? endDate.format(DATE_FMT) : null);
        params.put("dateRange", dateRange);

        return params;
    }

    // ====================================================================
    //                   比对分析参数构建
    // ====================================================================

    /**
     * 构建科室比对分析请求参数
     */
    public Map<String, Object> buildComparisonAnalysisParams(
            String labCode, String primaryInstrumentCode, String secondaryInstrumentCode,
            List<String> itemCodes, String comparisonMethod,
            BigDecimal acceptableBias, BigDecimal acceptableCv,
            LocalDate startDate, LocalDate endDate) {

        log.info("构建比对分析参数, labCode={}, primary={}, secondary={}",
                labCode, primaryInstrumentCode, secondaryInstrumentCode);

        Map<String, Object> params = new LinkedHashMap<>();

        // 基础参数
        params.put("apiUrl", COMPARISON_URL);
        params.put("apiKey", API_KEY);
        params.put("apiVersion", API_VERSION);
        params.put("timeout", DEFAULT_TIMEOUT * 2);
        params.put("requestId", UUID.randomUUID().toString());
        params.put("requestTime", LocalDateTime.now().format(DATETIME_FMT));
        params.put("analysisType", "COMPARISON");

        // 科室对信息
        Map<String, Object> instrumentPair = new LinkedHashMap<>();
        instrumentPair.put("primaryInstrumentCode", primaryInstrumentCode);
        instrumentPair.put("secondaryInstrumentCode", secondaryInstrumentCode);
        instrumentPair.put("labCode", labCode);
        params.put("instrumentPair", instrumentPair);

        // 项目列表
        if (!CollectionUtils.isEmpty(itemCodes)) {
            params.put("itemCodes", itemCodes);
            params.put("itemCount", itemCodes.size());
        }

        // 比对方法配置
        Map<String, Object> methodConfig = new LinkedHashMap<>();
        String method = StringUtils.hasText(comparisonMethod) ? comparisonMethod : "PASSING_BABLOK";
        methodConfig.put("method", method);
        methodConfig.put("methodName", getComparisonMethodName(method));

        // 根据不同比对方法设置参数
        switch (method) {
            case "PASSING_BABLOK":
                methodConfig.put("confidenceLevel", 0.95);
                methodConfig.put("bootstrapIterations", 1000);
                break;
            case "DEMING":
                methodConfig.put("errorRatio", 1.0);
                methodConfig.put("confidenceLevel", 0.95);
                break;
            case "BLAND_ALTMAN":
                methodConfig.put("confidenceLevel", 0.95);
                methodConfig.put("plotType", "DIFFERENCE");
                break;
            case "LINEAR_REGRESSION":
                methodConfig.put("forceIntercept", false);
                methodConfig.put("confidenceLevel", 0.95);
                break;
            default:
                log.warn("未知的比对方法: {}, 使用默认Passing-Bablok", method);
                methodConfig.put("method", "PASSING_BABLOK");
                methodConfig.put("confidenceLevel", 0.95);
                break;
        }
        params.put("comparisonMethod", methodConfig);

        // 可接受标准
        Map<String, Object> acceptanceCriteria = new LinkedHashMap<>();
        acceptanceCriteria.put("maxBias", acceptableBias != null ? acceptableBias.toPlainString() : "5.0");
        acceptanceCriteria.put("maxCv", acceptableCv != null ? acceptableCv.toPlainString() : "10.0");
        acceptanceCriteria.put("minCorrelationCoefficient", "0.975");
        acceptanceCriteria.put("minDataPairs", 40);
        acceptanceCriteria.put("evaluationStandard", "CLIA");
        params.put("acceptanceCriteria", acceptanceCriteria);

        // 时间范围
        Map<String, Object> dateRange = new LinkedHashMap<>();
        dateRange.put("startDate", startDate != null ? startDate.format(DATE_FMT) : null);
        dateRange.put("endDate", endDate != null ? endDate.format(DATE_FMT) : null);
        params.put("dateRange", dateRange);

        return params;
    }

    // ====================================================================
    //                   辅助方法
    // ====================================================================

    /**
     * 构建Westgard规则配置
     */
    private Map<String, Object> buildWestgardRuleConfig(String algorithmCode) {
        Map<String, Object> ruleConfig = new LinkedHashMap<>();

        // 默认启用的规则
        List<Map<String, Object>> rules = new ArrayList<>();

        Map<String, Object> rule13s = new LinkedHashMap<>();
        rule13s.put("code", "1-3s");
        rule13s.put("name", "单值超过3个标准差");
        rule13s.put("enabled", true);
        rule13s.put("level", "CRITICAL");
        rule13s.put("action", "REJECT");
        rules.add(rule13s);

        Map<String, Object> rule12s = new LinkedHashMap<>();
        rule12s.put("code", "1-2s");
        rule12s.put("name", "单值超过2个标准差");
        rule12s.put("enabled", true);
        rule12s.put("level", "WARNING");
        rule12s.put("action", "WARN");
        rules.add(rule12s);

        Map<String, Object> rule22s = new LinkedHashMap<>();
        rule22s.put("code", "2-2s");
        rule22s.put("name", "连续2值同侧超过2个标准差");
        rule22s.put("enabled", true);
        rule22s.put("level", "ERROR");
        rule22s.put("action", "REJECT");
        rules.add(rule22s);

        Map<String, Object> ruleR4s = new LinkedHashMap<>();
        ruleR4s.put("code", "R-4s");
        ruleR4s.put("name", "连续2值之差超过4个标准差");
        ruleR4s.put("enabled", true);
        ruleR4s.put("level", "ERROR");
        ruleR4s.put("action", "REJECT");
        rules.add(ruleR4s);

        Map<String, Object> rule41s = new LinkedHashMap<>();
        rule41s.put("code", "4-1s");
        rule41s.put("name", "连续4值同侧超过1个标准差");
        rule41s.put("enabled", true);
        rule41s.put("level", "WARNING");
        rule41s.put("action", "WARN");
        rules.add(rule41s);

        Map<String, Object> rule10x = new LinkedHashMap<>();
        rule10x.put("code", "10x");
        rule10x.put("name", "连续10值在均值同侧");
        rule10x.put("enabled", true);
        rule10x.put("level", "WARNING");
        rule10x.put("action", "WARN");
        rules.add(rule10x);

        ruleConfig.put("rules", rules);
        ruleConfig.put("multiRule", "WESTGARD".equals(algorithmCode));
        ruleConfig.put("cascadeReject", true);

        return ruleConfig;
    }

    /**
     * 获取比对方法名称
     */
    private String getComparisonMethodName(String method) {
        switch (method) {
            case "PASSING_BABLOK":
                return "Passing-Bablok回归";
            case "DEMING":
                return "Deming回归";
            case "BLAND_ALTMAN":
                return "Bland-Altman分析";
            case "LINEAR_REGRESSION":
                return "线性回归";
            default:
                return method;
        }
    }

    /**
     * 验证日期范围参数
     */
    public void validateDateRange(String startDateStr, String endDateStr) {
        if (!StringUtils.hasText(startDateStr) || !StringUtils.hasText(endDateStr)) {
            throw new CpBusinessException(CommonErrorCode.INVALID_PARAM, "日期范围不能为空");
        }

        try {
            LocalDate startDate = LocalDate.parse(startDateStr, DATE_FMT);
            LocalDate endDate = LocalDate.parse(endDateStr, DATE_FMT);

            if (startDate.isAfter(endDate)) {
                throw new CpBusinessException(CommonErrorCode.INVALID_PARAM,
                        "开始日期不能晚于结束日期");
            }

            if (startDate.isBefore(LocalDate.now().minusYears(2))) {
                throw new CpBusinessException(CommonErrorCode.INVALID_PARAM,
                        "查询时间范围不能超过2年");
            }
        } catch (DateTimeParseException e) {
            throw new CpBusinessException(CommonErrorCode.INVALID_PARAM,
                    "日期格式错误，请使用yyyy-MM-dd格式");
        }
    }

    /**
     * 构建通用请求头
     */
    public Map<String, String> buildCommonHeaders(String labCode) {
        Map<String, String> headers = new LinkedHashMap<>();
        headers.put("Content-Type", "application/json;charset=UTF-8");
        headers.put("X-Api-Key", API_KEY);
        headers.put("X-Api-Version", API_VERSION);
        headers.put("X-Lab-Code", labCode);
        headers.put("X-Request-Id", UUID.randomUUID().toString());
        headers.put("X-Timestamp", String.valueOf(System.currentTimeMillis()));
        return headers;
    }
}
