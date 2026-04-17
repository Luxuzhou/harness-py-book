package com.example.cp.dto.dataset;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 数据集统计摘要DTO
 *
 * @author cp-team
 * @since 2024-03-25
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DatasetSummaryDto {

    private String labCode;
    private String instrumentCode;
    private String itemCode;
    private LocalDate date;
    private Long totalCount;
    private Long qcCount;
    private Long patientCount;
    private BigDecimal mean;
    private BigDecimal sd;
    private BigDecimal cv;
    private BigDecimal median;
    private BigDecimal min;
    private BigDecimal max;
    private BigDecimal p25;
    private BigDecimal p75;
}
