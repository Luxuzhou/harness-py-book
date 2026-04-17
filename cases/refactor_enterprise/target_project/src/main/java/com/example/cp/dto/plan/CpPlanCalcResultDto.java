package com.example.cp.dto.plan;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 临床路径方案计算结果DTO
 *
 * @author cp-team
 * @since 2024-03-18
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CpPlanCalcResultDto {

    private String planId;
    private String itemCode;
    private String algorithmCode;
    private String algorithmName;
    private Integer movingWindow;
    private Integer dataCount;
    private BigDecimal calculatedMean;
    private BigDecimal calculatedSd;
    private BigDecimal calculatedCv;
    private BigDecimal targetMean;
    private BigDecimal targetSd;
    private List<BigDecimal> movingAverages;
    private List<Map<String, Object>> ruleViolations;
    private Boolean success;
    private String message;
    private LocalDateTime calcTime;
}
