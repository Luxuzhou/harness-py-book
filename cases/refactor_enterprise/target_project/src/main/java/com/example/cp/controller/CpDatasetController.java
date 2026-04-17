package com.example.cp.controller;

import com.example.cp.dto.dataset.DatasetQueryRequest;
import com.example.cp.dto.dataset.DatasetSummaryDto;
import com.example.cp.mapper.ck.BiTreatmentRecordMapper;
import com.example.cp.model.ck.BiTreatmentRecord;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

/**
 * 临床路径数据集管理接口
 *
 * @author cp-team
 * @since 2024-03-25
 */
@Slf4j
@RestController
@RequestMapping("/api/cp/dataset")
@RequiredArgsConstructor
@Validated
@Tag(name = "临床路径数据集", description = "临床路径诊疗数据的查询与统计")
public class CpDatasetController {

    private final BiTreatmentRecordMapper biInspectResultMapper;

    @GetMapping("/query")
    @Operation(summary = "查询诊疗数据", description = "从ClickHouse查询诊疗结果数据")
    public ResponseEntity<Map<String, Object>> queryData(
            @RequestParam @NotBlank(message = "实验室编码不能为空") String labCode,
            @RequestParam @NotBlank(message = "科室编码不能为空") String instrumentCode,
            @RequestParam @NotBlank(message = "项目编码不能为空") String itemCode,
            @RequestParam(required = false) @Parameter(description = "临床路径品批号") String controlLotNo,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd")
                @Parameter(description = "开始日期") LocalDate startDate,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd")
                @Parameter(description = "结束日期") LocalDate endDate) {

        if (startDate == null) startDate = LocalDate.now().minusDays(30);
        if (endDate == null) endDate = LocalDate.now();

        List<BiTreatmentRecord> results = biInspectResultMapper.queryByCondition(
                labCode, instrumentCode, itemCode, controlLotNo,
                startDate.atStartOfDay(), endDate.atTime(23, 59, 59));

        return ResponseEntity.ok(Map.of(
                "code", 200,
                "data", results,
                "total", results.size()
        ));
    }

    @GetMapping("/summary")
    @Operation(summary = "数据汇总统计", description = "获取指定条件下的诊疗数据统计摘要")
    public ResponseEntity<Map<String, Object>> getSummary(
            @RequestParam @NotBlank(message = "实验室编码不能为空") String labCode,
            @RequestParam(required = false) String instrumentCode,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate date) {

        if (date == null) date = LocalDate.now();

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("labCode", labCode);
        summary.put("date", date.toString());
        summary.put("queryTime", LocalDateTime.now().toString());

        return ResponseEntity.ok(Map.of("code", 200, "data", summary));
    }

    @GetMapping("/items")
    @Operation(summary = "查询可用项目列表", description = "查询指定科室上可用的诊疗环节")
    public ResponseEntity<Map<String, Object>> getAvailableItems(
            @RequestParam @NotBlank(message = "实验室编码不能为空") String labCode,
            @RequestParam @NotBlank(message = "科室编码不能为空") String instrumentCode) {

        // 简化实现：返回空列表
        return ResponseEntity.ok(Map.of("code", 200, "data", Collections.emptyList()));
    }
}
