package com.example.sqc.dto.client.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * 室内质控分析请求
 *
 * @author sqc-team
 * @since 2024-02-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class IqcAnalysisRequest {

    private String labCode;
    private String instrumentCode;
    private String itemCode;
    private String controlLotNo;
    private Integer controlLevel;
    private String algorithmCode;
    private Integer movingWindow;
    private BigDecimal targetMean;
    private BigDecimal targetSd;
    private LocalDate startDate;
    private LocalDate endDate;
    private List<BigDecimal> dataPoints;
    private Map<String, Object> ruleConfig;
    private Map<String, Object> extraParams;
}
