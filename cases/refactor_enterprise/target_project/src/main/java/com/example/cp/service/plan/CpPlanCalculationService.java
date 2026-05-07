package com.example.cp.service.plan;

import com.example.cp.dto.plan.CpPlanApplyRequest;
import com.example.cp.enums.plan.AlgorithmEnum;
import com.example.cp.enums.plan.TailProcessingEnum;
import com.example.cp.exception.CpBusinessException;
import com.example.cp.exception.CommonErrorCode;
import com.example.cp.mapper.CpPathwayPlanMapper;
import com.example.cp.mapper.CpComplianceRateMapper;
import com.example.cp.mapper.ck.BiTreatmentRecordMapper;
import com.example.cp.model.CpPathwayPlan;
import com.example.cp.model.CpComplianceRate;
import com.example.cp.model.ck.BiTreatmentRecord;
import com.example.cp.service.monitor.CpDeviationService;
import com.example.cp.service.plan.support.CpPlanStatisticsHelper;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 临床路径方案计算服务
 * <p>
 * 负责临床路径算法的核心计算流程：数据采集、预处理、正态转换、
 * 移动平均、统计量计算、Westgard规则判定、结果持久化。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CpPlanCalculationService {

    private final CpPathwayPlanMapper cpPathwayPlanMapper;
    private final CpComplianceRateMapper cpComplianceRateMapper;
    private final BiTreatmentRecordMapper biInspectResultMapper;
    private final CpDeviationService cpDeviationService;

    private static final int DEFAULT_MOVING_WINDOW = 20;

    /**
     * 应用临床路径路径依从率计划（15参数版本，兼容Controller调用）
     */
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> applyCpPathwayPlan(
            String planId, String labCode, String instrumentCode, String itemCode,
            String controlLotNo, Integer controlLevel, String algorithmCode,
            Integer movingWindow, BigDecimal targetMean, BigDecimal targetSd,
            String normalTransCode, String tailProcessing, Boolean excludeWeekend,
            LocalDate startDate, LocalDate endDate) {

        CpPlanApplyRequest request = CpPlanApplyRequest.builder()
                .planId(planId)
                .labCode(labCode)
                .instrumentCode(instrumentCode)
                .itemCode(itemCode)
                .controlLotNo(controlLotNo)
                .controlLevel(controlLevel)
                .algorithmCode(algorithmCode)
                .movingWindow(movingWindow)
                .targetMean(targetMean)
                .targetSd(targetSd)
                .normalTransCode(normalTransCode)
                .tailProcessing(tailProcessing)
                .excludeWeekend(excludeWeekend)
                .startDate(startDate)
                .endDate(endDate)
                .build();

        return applyCpPathwayPlan(request);
    }

    /**
     * 应用临床路径路径依从率计划（推荐使用CpPlanApplyRequest参数对象）
     */
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> applyCpPathwayPlan(CpPlanApplyRequest request) {
        String planId = request.getPlanId();
        String labCode = request.getLabCode();
        String instrumentCode = request.getInstrumentCode();
        String itemCode = request.getItemCode();
        String algorithmCode = request.getAlgorithmCode();
        Integer movingWindow = request.getMovingWindow();
        LocalDate startDate = request.getStartDate();
        LocalDate endDate = request.getEndDate();

        log.info("开始应用临床路径路径依从率计划, planId={}, itemCode={}, algorithm={}, window={}",
                planId, itemCode, algorithmCode, movingWindow);

        // 参数校验
        if (!StringUtils.hasText(planId)) {
            throw new CpBusinessException(CommonErrorCode.INVALID_PARAM, "计划ID不能为空");
        }
        if (!StringUtils.hasText(labCode)) {
            throw new CpBusinessException(CommonErrorCode.INVALID_PARAM, "实验室编码不能为空");
        }
        if (movingWindow == null || movingWindow < 5) {
            movingWindow = DEFAULT_MOVING_WINDOW;
        }
        if (startDate == null) {
            startDate = LocalDate.now().minusDays(30);
        }
        if (endDate == null) {
            endDate = LocalDate.now();
        }

        // 步骤1：从ClickHouse采集诊疗数据
        List<BiTreatmentRecord> rawResults = biInspectResultMapper.queryByCondition(
                labCode, instrumentCode, itemCode, request.getControlLotNo(),
                startDate.atStartOfDay(), endDate.atTime(23, 59, 59));

        if (CollectionUtils.isEmpty(rawResults)) {
            log.warn("未查询到诊疗数据, itemCode={}, dateRange=[{}, {}]", itemCode, startDate, endDate);
            Map<String, Object> emptyResult = new HashMap<>();
            emptyResult.put("success", false);
            emptyResult.put("message", "未查询到诊疗数据");
            emptyResult.put("dataCount", 0);
            return emptyResult;
        }

        log.info("采集到诊疗数据 {} 条, itemCode={}", rawResults.size(), itemCode);

        // 步骤2：数据预处理 - 排除周末数据
        List<BiTreatmentRecord> filteredResults = rawResults;
        if (Boolean.TRUE.equals(request.getExcludeWeekend())) {
            filteredResults = rawResults.stream()
                    .filter(r -> {
                        if (r.getInspectTime() == null) return true;
                        int dayOfWeek = r.getInspectTime().toLocalDate().getDayOfWeek().getValue();
                        return dayOfWeek != 6 && dayOfWeek != 7;
                    })
                    .collect(Collectors.toList());
            log.info("排除周末后剩余 {} 条数据", filteredResults.size());
        }

        // 步骤3：提取数值并正态转换
        List<BigDecimal> values = filteredResults.stream()
                .map(BiTreatmentRecord::getResultValue)
                .filter(Objects::nonNull)
                .collect(Collectors.toList());

        if (StringUtils.hasText(request.getNormalTransCode())) {
            values = CpPlanStatisticsHelper.applyNormalTransform(values, request.getNormalTransCode());
        }

        // 步骤4：计算移动平均值
        List<BigDecimal> movingAverages = CpPlanStatisticsHelper.calculateMovingAverage(values, movingWindow);

        // 步骤5：计算统计量
        BigDecimal calculatedMean = CpPlanStatisticsHelper.calculateMean(movingAverages);
        BigDecimal calculatedSd = CpPlanStatisticsHelper.calculateStandardDeviation(movingAverages, calculatedMean);
        BigDecimal calculatedCv = BigDecimal.ZERO;
        if (calculatedMean.compareTo(BigDecimal.ZERO) != 0) {
            calculatedCv = calculatedSd.divide(calculatedMean, 4, RoundingMode.HALF_UP)
                    .multiply(new BigDecimal("100"));
        }

        // 步骤6：尾数处理
        if (StringUtils.hasText(request.getTailProcessing())) {
            TailProcessingEnum tailEnum = TailProcessingEnum.fromCode(request.getTailProcessing());
            if (tailEnum != null) {
                int scale = tailEnum.getDecimalPlaces();
                calculatedMean = calculatedMean.setScale(scale, RoundingMode.HALF_UP);
                calculatedSd = calculatedSd.setScale(scale, RoundingMode.HALF_UP);
                calculatedCv = calculatedCv.setScale(scale, RoundingMode.HALF_UP);
            }
        }

        // 步骤7：应用Westgard规则判定
        AlgorithmEnum algorithm = AlgorithmEnum.fromCode(algorithmCode);
        BigDecimal finalMean = request.getTargetMean() != null ? request.getTargetMean() : calculatedMean;
        BigDecimal finalSd = request.getTargetSd() != null ? request.getTargetSd() : calculatedSd;
        List<Map<String, Object>> ruleViolations = CpPlanStatisticsHelper.applyWestgardRules(
                movingAverages, finalMean, finalSd);

        // 步骤8：保存路径依从率记录
        saveMovingAvgRecords(planId, itemCode, instrumentCode, movingAverages,
                calculatedMean, calculatedSd, calculatedCv);

        // 步骤9：生成异常预警
        if (!CollectionUtils.isEmpty(ruleViolations)) {
            cpDeviationService.generateAlarms(planId, ruleViolations);
        }

        // 步骤10：更新计划状态
        CpPathwayPlan plan = cpPathwayPlanMapper.selectOneById(planId);
        if (plan != null) {
            plan.setLastCalcTime(LocalDateTime.now());
            plan.setCalcMean(calculatedMean);
            plan.setCalcSd(calculatedSd);
            plan.setCalcCv(calculatedCv);
            plan.setDataCount(filteredResults.size());
            plan.setUpdateTime(LocalDateTime.now());
            cpPathwayPlanMapper.update(plan);
        }

        // 组装返回结果
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("success", true);
        result.put("planId", planId);
        result.put("itemCode", itemCode);
        result.put("algorithmCode", algorithmCode);
        result.put("algorithmName", algorithm != null ? algorithm.getName() : "");
        result.put("movingWindow", movingWindow);
        result.put("dataCount", filteredResults.size());
        result.put("calculatedMean", calculatedMean);
        result.put("calculatedSd", calculatedSd);
        result.put("calculatedCv", calculatedCv);
        result.put("targetMean", request.getTargetMean());
        result.put("targetSd", request.getTargetSd());
        result.put("movingAverages", movingAverages);
        result.put("ruleViolations", ruleViolations);
        result.put("calcTime", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));

        log.info("临床路径路径依从率计划应用完成, planId={}, dataCount={}, violations={}",
                planId, filteredResults.size(), ruleViolations.size());

        return result;
    }

    /**
     * 保存路径依从率记录
     */
    private void saveMovingAvgRecords(String planId, String itemCode, String instrumentCode,
                                       List<BigDecimal> movingAverages,
                                       BigDecimal mean, BigDecimal sd, BigDecimal cv) {
        CpComplianceRate avg = new CpComplianceRate();
        avg.setId(UUID.randomUUID().toString().replace("-", ""));
        avg.setPlanId(planId);
        avg.setItemCode(itemCode);
        avg.setInstrumentCode(instrumentCode);
        avg.setAvgMean(mean);
        avg.setAvgSd(sd);
        avg.setAvgCv(cv);
        avg.setDataCount(movingAverages.size());
        avg.setCalcDate(LocalDate.now());
        avg.setCreateTime(LocalDateTime.now());

        cpComplianceRateMapper.insert(avg);
    }
}
