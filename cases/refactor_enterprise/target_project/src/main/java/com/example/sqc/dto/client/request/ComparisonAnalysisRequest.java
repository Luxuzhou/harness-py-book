package com.example.sqc.dto.client.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

/**
 * 仪器比对分析请求
 *
 * @author sqc-team
 * @since 2024-02-25
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ComparisonAnalysisRequest {

    private String labCode;
    private String primaryInstrumentCode;
    private String secondaryInstrumentCode;
    private List<String> itemCodes;
    private String comparisonMethod;
    private BigDecimal acceptableBias;
    private BigDecimal acceptableCv;
    private LocalDate startDate;
    private LocalDate endDate;
    private Integer minDataPairs;
}
