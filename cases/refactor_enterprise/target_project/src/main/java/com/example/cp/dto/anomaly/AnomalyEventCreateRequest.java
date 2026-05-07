package com.example.cp.dto.anomaly;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 创建异常事件请求 DTO
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "创建异常事件请求")
public class AnomalyEventCreateRequest {

    @NotNull(message = "规则ID不能为空")
    @Schema(description = "关联的预警规则ID", example = "1")
    private Long ruleId;

    @NotBlank(message = "诊疗项目ID不能为空")
    @Size(max = 64, message = "诊疗项目ID长度不能超过64")
    @Schema(description = "诊疗项目ID", example = "GLU-001", maxLength = 64)
    private String testItemId;

    @NotNull(message = "触发时间不能为空")
    @Schema(description = "异常预警触发时间", example = "2024-03-20T10:30:00")
    private LocalDateTime triggeredAt;

    @NotBlank(message = "严重程度不能为空")
    @Pattern(regexp = "^(WARNING|CRITICAL)$", message = "严重程度必须是 WARNING 或 CRITICAL")
    @Schema(description = "严重程度: WARNING/CRITICAL", example = "WARNING")
    private String severity;

    @Schema(description = "触发时的路径依从率序列")
    private List<Double> movingAverages;

    @Schema(description = "超限点位信息")
    private List<DeviationPoint> deviationPoints;

    @Size(max = 512, message = "描述信息长度不能超过512")
    @Schema(description = "异常预警描述信息", maxLength = 512)
    private String message;
}
