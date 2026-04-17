package com.example.cp.dto.plan;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 临床路径方案导出VO
 *
 * @author cp-team
 * @since 2024-04-01
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CpPlanExportVo {

    private String itemCode;
    private String itemName;
    private String instrumentName;
    private String algorithmName;
    private Integer movingWindow;
    private BigDecimal targetMean;
    private BigDecimal targetSd;
    private BigDecimal calcMean;
    private BigDecimal calcSd;
    private BigDecimal calcCv;
    private Integer dataCount;
    private String planStatusName;
    private String calcDate;
    private String createTime;
}
