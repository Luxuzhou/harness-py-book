package com.example.sqc.controller;

import com.example.sqc.dto.plan.SqcPlanBatchRequest;
import com.example.sqc.dto.plan.SqcPlanCreateRequest;
import com.example.sqc.dto.plan.SqcPlanDto;
import com.example.sqc.dto.plan.SqcPlanPageRequest;
import com.example.sqc.dto.plan.SqcPlanUpdateRequest;
import com.example.sqc.model.SqcMovingChange;
import com.example.sqc.service.plan.SqcPlanService;

import com.mybatisflex.core.paginate.Page;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * 质控计划管理接口
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Slf4j
@RestController
@RequestMapping("/api/sqc/plan")
@RequiredArgsConstructor
@Validated
@Tag(name = "质控计划管理", description = "质控计划的增删改查、算法应用、批量操作等")
public class SqcPlanController {

    private final SqcPlanService sqcPlanService;

    // ====================================================================
    //                         基本CRUD
    // ====================================================================

    @PostMapping("/create")
    @Operation(summary = "创建质控计划", description = "创建新的质控移动均值计划")
    public ResponseEntity<Map<String, Object>> createPlan(@Valid @RequestBody SqcPlanCreateRequest request) {
        log.info("创建质控计划请求, itemCode={}, instrumentCode={}", request.getItemCode(), request.getInstrumentCode());
        SqcPlanDto dto = sqcPlanService.createPlan(request);
        return ResponseEntity.ok(Map.of("code", 200, "message", "创建成功", "data", dto));
    }

    @PutMapping("/update/{planId}")
    @Operation(summary = "更新质控计划", description = "更新现有质控计划的配置参数")
    public ResponseEntity<Map<String, Object>> updatePlan(
            @PathVariable @NotBlank(message = "计划ID不能为空") String planId,
            @Valid @RequestBody SqcPlanUpdateRequest request) {
        log.info("更新质控计划请求, planId={}", planId);
        SqcPlanDto dto = sqcPlanService.updatePlan(planId, request);
        return ResponseEntity.ok(Map.of("code", 200, "message", "更新成功", "data", dto));
    }

    @DeleteMapping("/delete/{planId}")
    @Operation(summary = "删除质控计划", description = "逻辑删除质控计划")
    public ResponseEntity<Map<String, Object>> deletePlan(
            @PathVariable @NotBlank(message = "计划ID不能为空") String planId,
            @RequestParam @NotBlank(message = "操作人不能为空") String operator) {
        log.info("删除质控计划请求, planId={}, operator={}", planId, operator);
        sqcPlanService.deletePlan(planId, operator);
        return ResponseEntity.ok(Map.of("code", 200, "message", "删除成功"));
    }

    @GetMapping("/detail/{planId}")
    @Operation(summary = "查询计划详情", description = "根据ID查询质控计划详情")
    public ResponseEntity<Map<String, Object>> getPlanDetail(
            @PathVariable @NotBlank(message = "计划ID不能为空") String planId) {
        SqcPlanDto dto = sqcPlanService.getPlanById(planId);
        return ResponseEntity.ok(Map.of("code", 200, "data", dto));
    }

    // ====================================================================
    //                         列表查询（大量@RequestParam）
    // ====================================================================

    @GetMapping("/page")
    @Operation(summary = "分页查询计划", description = "按条件分页查询质控计划列表")
    public ResponseEntity<Map<String, Object>> queryPlanPage(
            @RequestParam(required = false) @Parameter(description = "实验室编码") String labCode,
            @RequestParam(required = false) @Parameter(description = "仪器编码") String instrumentCode,
            @RequestParam(required = false) @Parameter(description = "项目编码") String itemCode,
            @RequestParam(required = false) @Parameter(description = "计划状态(0=禁用,1=启用)") Integer planStatus,
            @RequestParam(required = false) @Parameter(description = "算法编码") String algorithmCode,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd")
                @Parameter(description = "创建开始日期") LocalDate startDate,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd")
                @Parameter(description = "创建结束日期") LocalDate endDate,
            @RequestParam(defaultValue = "1") @Parameter(description = "页码") Integer pageNum,
            @RequestParam(defaultValue = "20") @Parameter(description = "每页大小") Integer pageSize) {

        SqcPlanPageRequest request = new SqcPlanPageRequest();
        request.setLabCode(labCode);
        request.setInstrumentCode(instrumentCode);
        request.setItemCode(itemCode);
        request.setPlanStatus(planStatus);
        request.setAlgorithmCode(algorithmCode);
        request.setStartDate(startDate);
        request.setEndDate(endDate);
        request.setPageNum(pageNum);
        request.setPageSize(pageSize);

        Page<SqcPlanDto> page = sqcPlanService.queryPlanPage(request);
        return ResponseEntity.ok(Map.of("code", 200, "data", page));
    }

    @GetMapping("/list")
    @Operation(summary = "查询计划列表", description = "按实验室和仪器查询计划列表")
    public ResponseEntity<Map<String, Object>> queryPlanList(
            @RequestParam @NotBlank(message = "实验室编码不能为空") String labCode,
            @RequestParam @NotBlank(message = "仪器编码不能为空") String instrumentCode) {
        List<SqcPlanDto> list = sqcPlanService.queryPlansByLabAndInstrument(labCode, instrumentCode);
        return ResponseEntity.ok(Map.of("code", 200, "data", list));
    }

    // ====================================================================
    //                         算法应用（参数非常多）
    // ====================================================================

    @PostMapping("/apply")
    @Operation(summary = "应用质控算法", description = "将质控移动均值算法应用到指定的检验数据上")
    public ResponseEntity<Map<String, Object>> applySqcMovingPlan(
            @RequestParam @NotBlank(message = "计划ID不能为空")
                @Parameter(description = "计划ID") String planId,
            @RequestParam @NotBlank(message = "实验室编码不能为空")
                @Parameter(description = "实验室编码") String labCode,
            @RequestParam @NotBlank(message = "仪器编码不能为空")
                @Parameter(description = "仪器编码") String instrumentCode,
            @RequestParam @NotBlank(message = "项目编码不能为空")
                @Parameter(description = "项目编码") String itemCode,
            @RequestParam(required = false)
                @Parameter(description = "质控品批号") String controlLotNo,
            @RequestParam(required = false)
                @Parameter(description = "质控品水平") Integer controlLevel,
            @RequestParam(defaultValue = "WESTGARD")
                @Parameter(description = "算法编码") String algorithmCode,
            @RequestParam(defaultValue = "20")
                @Parameter(description = "移动窗口大小") Integer movingWindow,
            @RequestParam(required = false)
                @Parameter(description = "目标均值") BigDecimal targetMean,
            @RequestParam(required = false)
                @Parameter(description = "目标标准差") BigDecimal targetSd,
            @RequestParam(required = false)
                @Parameter(description = "正态转换算法编码") String normalTransCode,
            @RequestParam(required = false)
                @Parameter(description = "尾数处理方式") String tailProcessing,
            @RequestParam(required = false)
                @Parameter(description = "是否排除周末") Boolean excludeWeekend,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd")
                @Parameter(description = "开始日期") LocalDate startDate,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd")
                @Parameter(description = "结束日期") LocalDate endDate) {

        Map<String, Object> result = sqcPlanService.applySqcMovingPlan(
                planId, labCode, instrumentCode, itemCode, controlLotNo, controlLevel,
                algorithmCode, movingWindow, targetMean, targetSd,
                normalTransCode, tailProcessing, excludeWeekend, startDate, endDate);

        return ResponseEntity.ok(Map.of("code", 200, "data", result));
    }

    // ====================================================================
    //                         批量操作
    // ====================================================================

    @PostMapping("/batch/status")
    @Operation(summary = "批量更新计划状态", description = "批量启用或禁用质控计划")
    public ResponseEntity<Map<String, Object>> batchUpdateStatus(
            @Valid @RequestBody SqcPlanBatchRequest request) {
        int count = sqcPlanService.batchUpdatePlanStatus(request);
        return ResponseEntity.ok(Map.of("code", 200, "message", "批量更新成功", "count", count));
    }

    @PostMapping("/batch/calc")
    @Operation(summary = "批量执行计算", description = "批量执行质控移动均值计算")
    public ResponseEntity<Map<String, Object>> batchExecuteCalc(
            @RequestBody List<String> planIds) {
        List<Map<String, Object>> results = sqcPlanService.batchExecutePlanCalc(planIds);
        return ResponseEntity.ok(Map.of("code", 200, "data", results));
    }

    // ====================================================================
    //                         变更查询
    // ====================================================================

    @GetMapping("/changes/{planId}")
    @Operation(summary = "查询变更历史", description = "查询计划配置的变更记录")
    public ResponseEntity<Map<String, Object>> queryPlanChanges(
            @PathVariable String planId,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate startDate,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate endDate) {
        List<SqcMovingChange> changes = sqcPlanService.queryPlanChanges(planId, startDate, endDate);
        return ResponseEntity.ok(Map.of("code", 200, "data", changes));
    }

    // ====================================================================
    //                         统计
    // ====================================================================

    @GetMapping("/stats/count")
    @Operation(summary = "统计计划数量", description = "按状态统计各类计划数量")
    public ResponseEntity<Map<String, Object>> countByStatus(
            @RequestParam @NotBlank(message = "实验室编码不能为空") String labCode) {
        Map<String, Long> counts = sqcPlanService.countPlanByStatus(labCode);
        return ResponseEntity.ok(Map.of("code", 200, "data", counts));
    }
}
