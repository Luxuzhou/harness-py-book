package com.example.cp.dto.client.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * 室间质评分析请求
 *
 * @author cp-team
 * @since 2024-02-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class EqaAnalysisRequest {

    private String labCode;
    private String instrumentCode;
    private List<String> itemCodes;
    private String eqaProgramCode;
    private String eqaYear;
    private String eqaBatch;
    private List<Map<String, Object>> eqaResults;
    private String evaluationMethod;
    private Map<String, Object> evaluationConfig;
}
