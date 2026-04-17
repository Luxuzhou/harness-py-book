package com.example.cp.dto.plan;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 临床路径方案应用请求（封装15参数方法应有的参数对象）
 * <p>
 * 注意：当前CpPlanService.applyCpPathwayPlan()方法直接接收15个参数，
 * 这个DTO是"正确做法"的参考，但实际上并未被使用——这也是一个坏味道。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-18
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CpPlanApplyRequest {

    @NotBlank(message = "计划ID不能为空")
    private String planId;

    @NotBlank(message = "实验室编码不能为空")
    private String labCode;

    @NotBlank(message = "科室编码不能为空")
    private String instrumentCode;

    @NotBlank(message = "项目编码不能为空")
    private String itemCode;

    private String controlLotNo;

    private Integer controlLevel;

    private String algorithmCode;

    @Positive(message = "移动窗口必须为正整数")
    private Integer movingWindow;

    private BigDecimal targetMean;

    private BigDecimal targetSd;

    private String normalTransCode;

    private String tailProcessing;

    private Boolean excludeWeekend;

    private LocalDate startDate;

    private LocalDate endDate;
}
