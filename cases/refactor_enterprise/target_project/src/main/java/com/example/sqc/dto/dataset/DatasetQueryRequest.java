package com.example.sqc.dto.dataset;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

/**
 * 数据集查询请求
 *
 * @author sqc-team
 * @since 2024-03-25
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DatasetQueryRequest {

    @NotBlank(message = "实验室编码不能为空")
    private String labCode;

    @NotBlank(message = "仪器编码不能为空")
    private String instrumentCode;

    @NotBlank(message = "项目编码不能为空")
    private String itemCode;

    private String controlLotNo;

    private Integer controlLevel;

    private Integer sampleType;

    private Boolean isQcData;

    private LocalDate startDate;

    private LocalDate endDate;

    private Integer pageNum = 1;

    private Integer pageSize = 100;
}
