package com.example.cp.dto.anomaly;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 异常事件响应 DTO
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "异常事件响应")
public class AnomalyEventResponse {

    @Schema(description = "事件ID")
    private Long id;

    @Schema(description = "关联的预警规则ID")
    private Long ruleId;

    @Schema(description = "诊疗项目ID")
    private String testItemId;

    @Schema(description = "异常预警触发时间")
    private LocalDateTime triggeredAt;

    @Schema(description = "严重程度")
    private String severity;

    @Schema(description = "异常预警描述信息")
    private String message;

    @Schema(description = "创建时间")
    private LocalDateTime createdAt;
}
