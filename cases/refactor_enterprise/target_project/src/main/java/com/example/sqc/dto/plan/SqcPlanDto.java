package com.example.sqc.dto.plan;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 质控计划DTO
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SqcPlanDto {

    private String id;
    private String labCode;
    private String labName;
    private String instrumentCode;
    private String instrumentName;
    private String itemCode;
    private String itemName;
    private String itemAbbr;
    private String controlLotNo;
    private Integer controlLevel;
    private String controlName;
    private String algorithmCode;
    private String algorithmName;
    private String algorithmDesc;
    private Integer movingWindow;
    private BigDecimal targetMean;
    private BigDecimal targetSd;
    private BigDecimal targetCv;
    private BigDecimal calcMean;
    private BigDecimal calcSd;
    private BigDecimal calcCv;
    private Integer dataCount;
    private String normalTransCode;
    private String normalTransName;
    private String tailProcessing;
    private Boolean excludeWeekend;
    private Integer planStatus;
    private String planStatusName;
    private LocalDateTime lastCalcTime;
    private String creator;
    private String updater;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private String remark;

    // 关联统计信息
    private BigDecimal latestMean;
    private BigDecimal latestSd;
    private BigDecimal latestCv;
    private LocalDate latestCalcDate;
    private Integer sampleCount;
    private Integer recentAlarmCount;
}
