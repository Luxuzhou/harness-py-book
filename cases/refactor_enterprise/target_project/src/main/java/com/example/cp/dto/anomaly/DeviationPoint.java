package com.example.cp.dto.anomaly;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 超限点位信息 DTO
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "超限点位信息")
public class DeviationPoint {

    @Schema(description = "超限点在序列中的位置索引")
    private Integer index;

    @Schema(description = "该点的路径依从率")
    private Double movingAverage;

    @Schema(description = "上控制限")
    private Double upperLimit;

    @Schema(description = "下控制限")
    private Double lowerLimit;

    @Schema(description = "超限方向: HIGH/LOW")
    private String direction;
}
