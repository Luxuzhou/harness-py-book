package com.example.sqc.dto.plan;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 质控计划批量操作请求
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SqcPlanBatchRequest {

    @NotEmpty(message = "计划ID列表不能为空")
    private List<String> planIds;

    @NotNull(message = "目标状态不能为空")
    private Integer targetStatus;

    @NotBlank(message = "操作人不能为空")
    private String operator;

    private String reason;
}
