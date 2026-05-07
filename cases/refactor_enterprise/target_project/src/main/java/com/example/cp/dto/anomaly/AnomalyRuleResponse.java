package com.example.cp.dto.anomaly;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 预警规则响应 DTO
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "预警规则响应")
public class AnomalyRuleResponse {

    @Schema(description = "规则ID")
    private Long id;

    @Schema(description = "诊疗项目ID")
    private String testItemId;

    @Schema(description = "诊疗项目名称")
    private String testItemName;

    @Schema(description = "路径依从率窗口大小")
    private Integer windowSize;

    @Schema(description = "连续超限判定次数")
    private Integer consecutiveCount;

    @Schema(description = "控制限倍数（相对于SD）")
    private BigDecimal thresholdMultiplier;

    @Schema(description = "目标值（靶值）")
    private BigDecimal targetValue;

    @Schema(description = "标准差")
    private BigDecimal sdValue;

    @Schema(description = "是否启用")
    private Boolean enabled;

    @Schema(description = "创建时间")
    private LocalDateTime createdAt;

    @Schema(description = "更新时间")
    private LocalDateTime updatedAt;
}
