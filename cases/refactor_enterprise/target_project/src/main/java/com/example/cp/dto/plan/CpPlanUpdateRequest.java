package com.example.cp.dto.plan;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 临床路径方案更新请求
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CpPlanUpdateRequest {

    private String algorithmCode;
    private Integer movingWindow;
    private BigDecimal targetMean;
    private BigDecimal targetSd;
    private BigDecimal targetCv;
    private String controlLotNo;
    private Integer controlLevel;
    private String controlName;
    private String normalTransCode;
    private String tailProcessing;
    private Boolean excludeWeekend;
    private Integer planStatus;
    private String remark;

    @NotBlank(message = "操作人不能为空")
    private String operator;
}
