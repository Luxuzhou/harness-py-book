package com.example.sqc.dto.export;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

/**
 * 数据导出请求
 *
 * @author sqc-team
 * @since 2024-04-01
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ExportRequest {

    @NotBlank(message = "计划ID不能为空")
    private String planId;

    private String exportType;

    private String fileFormat;

    private LocalDate startDate;

    private LocalDate endDate;

    private Boolean includeAlarms;

    private Boolean includeChanges;

    private String operator;
}
