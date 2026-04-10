package com.example.sqc.dto.monitor;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 报警处理请求
 *
 * @author sqc-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AlarmHandleRequest {

    @NotBlank(message = "报警ID不能为空")
    private String alarmId;

    @NotNull(message = "处理状态不能为空")
    private Integer handleStatus;

    @NotBlank(message = "处理人不能为空")
    private String handler;

    private String handleRemark;
}
