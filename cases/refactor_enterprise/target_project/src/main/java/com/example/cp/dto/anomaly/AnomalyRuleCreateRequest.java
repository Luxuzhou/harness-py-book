package com.example.cp.dto.anomaly;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 创建预警规则请求 DTO
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "创建预警规则请求")
public class AnomalyRuleCreateRequest {

    @NotBlank(message = "诊疗项目ID不能为空")
    @Size(max = 64, message = "诊疗项目ID长度不能超过64")
    @Schema(description = "诊疗项目ID", example = "GLU-001", maxLength = 64)
    private String testItemId;

    @NotBlank(message = "诊疗项目名称不能为空")
    @Size(max = 128, message = "诊疗项目名称长度不能超过128")
    @Schema(description = "诊疗项目名称", example = "血糖 GLU", maxLength = 128)
    private String testItemName;

    @Min(value = 3, message = "窗口大小不能小于3")
    @Max(value = 20, message = "窗口大小不能大于20")
    @Schema(description = "路径依从率窗口大小", example = "5", defaultValue = "5")
    private Integer windowSize = 5;

    @Min(value = 2, message = "连续超限次数不能小于2")
    @Max(value = 10, message = "连续超限次数不能大于10")
    @Schema(description = "连续超限判定次数", example = "3", defaultValue = "3")
    private Integer consecutiveCount = 3;

    @DecimalMin(value = "0.5", message = "阈值倍数不能小于0.5")
    @DecimalMax(value = "3.0", message = "阈值倍数不能大于3.0")
    @Schema(description = "控制限倍数（相对于SD）", example = "1.5", defaultValue = "1.5")
    private BigDecimal thresholdMultiplier = new BigDecimal("1.5");

    @NotNull(message = "目标值不能为空")
    @Schema(description = "目标值（靶值）", example = "5.5")
    private BigDecimal targetValue;

    @NotNull(message = "标准差不能为空")
    @Schema(description = "标准差", example = "0.3")
    private BigDecimal sdValue;

    @Schema(description = "是否启用", example = "true", defaultValue = "true")
    private Boolean enabled = true;
}
