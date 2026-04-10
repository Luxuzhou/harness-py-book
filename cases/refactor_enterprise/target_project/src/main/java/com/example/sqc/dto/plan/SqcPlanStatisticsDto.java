package com.example.sqc.dto.plan;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 质控计划统计DTO
 *
 * @author sqc-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SqcPlanStatisticsDto {

    private String labCode;
    private String instrumentCode;
    private String itemCode;
    private Long totalPlans;
    private Long activePlans;
    private Long disabledPlans;
    private BigDecimal avgCv;
    private BigDecimal avgSd;
    private Integer totalAlarms;
    private Integer criticalAlarms;
    private LocalDate statisticsDate;
}
