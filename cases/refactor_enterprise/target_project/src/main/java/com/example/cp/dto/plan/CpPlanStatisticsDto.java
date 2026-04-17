package com.example.cp.dto.plan;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 临床路径方案统计DTO
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CpPlanStatisticsDto {

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
