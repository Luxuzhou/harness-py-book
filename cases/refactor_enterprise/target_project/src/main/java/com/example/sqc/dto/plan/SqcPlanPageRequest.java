package com.example.sqc.dto.plan;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

/**
 * 质控计划分页查询请求
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SqcPlanPageRequest {

    private String labCode;
    private String instrumentCode;
    private String itemCode;
    private Integer planStatus;
    private String algorithmCode;
    private LocalDate startDate;
    private LocalDate endDate;
    private Integer pageNum = 1;
    private Integer pageSize = 20;
}
