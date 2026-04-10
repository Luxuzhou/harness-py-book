package com.example.sqc.dto.client.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 第三方分析引擎响应DTO
 *
 * @author sqc-team
 * @since 2024-02-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AnalysisResponseDto {

    private String requestId;
    private String analysisType;
    private Boolean success;
    private String errorCode;
    private String errorMessage;
    private Integer dataPointCount;
    private BigDecimal calculatedMean;
    private BigDecimal calculatedSd;
    private BigDecimal calculatedCv;
    private BigDecimal calculatedMedian;
    private List<BigDecimal> movingAverages;
    private List<Map<String, Object>> ruleViolations;
    private Map<String, Object> statisticsResult;
    private Map<String, Object> regressionResult;
    private Long processingTimeMs;
    private String responseTime;
}
