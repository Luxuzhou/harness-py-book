package com.example.cp.dto.plan;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 临床路径方案创建请求
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CpPlanCreateRequest {

    @NotBlank(message = "实验室编码不能为空")
    private String labCode;

    private String labName;

    @NotBlank(message = "科室编码不能为空")
    private String instrumentCode;

    private String instrumentName;

    @NotBlank(message = "诊疗环节编码不能为空")
    private String itemCode;

    private String itemName;

    private String itemAbbr;

    private String controlLotNo;

    private Integer controlLevel;

    private String controlName;

    @NotBlank(message = "算法编码不能为空")
    private String algorithmCode;

    @Positive(message = "移动窗口必须为正整数")
    private Integer movingWindow;

    private BigDecimal targetMean;

    private BigDecimal targetSd;

    private BigDecimal targetCv;

    private String normalTransCode;

    private String tailProcessing;

    private Boolean excludeWeekend;

    @NotBlank(message = "操作人不能为空")
    private String operator;

    private String remark;
}
