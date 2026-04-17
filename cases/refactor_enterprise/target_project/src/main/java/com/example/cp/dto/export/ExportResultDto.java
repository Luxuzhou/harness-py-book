package com.example.cp.dto.export;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 导出结果DTO
 *
 * @author cp-team
 * @since 2024-04-01
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ExportResultDto {

    private String taskId;
    private String planId;
    private String exportType;
    private String fileFormat;
    private String fileName;
    private String fileUrl;
    private Long fileSize;
    private String status;
    private Integer progress;
    private String errorMessage;
    private LocalDateTime createTime;
    private LocalDateTime completeTime;
}
