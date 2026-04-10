package com.example.sqc.dto.client.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.util.Map;

/**
 * 患者数据分析请求
 *
 * @author sqc-team
 * @since 2024-02-25
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PatientDataAnalysisRequest {

    private String labCode;
    private String instrumentCode;
    private String itemCode;
    private Integer sampleType;
    private String methodCode;
    private LocalDate startDate;
    private LocalDate endDate;
    private Map<String, Object> patientFilters;
    private Map<String, Object> statisticsConfig;
}
