package com.example.cp.service.plan;

import com.example.cp.bo.task.PlanTaskBo;
import com.example.cp.dto.plan.CpPlanDto;
import com.example.cp.enums.plan.AlgorithmEnum;
import com.example.cp.enums.plan.NormalTransAlgorithmEnum;
import com.example.cp.mapper.CpComplianceRateMapper;
import com.example.cp.mapper.CpClinicalVisitMapper;
import com.example.cp.model.CpPathwayPlan;
import com.example.cp.model.CpComplianceRate;
import com.example.cp.service.monitor.CpDeviationService;

import com.mybatisflex.core.query.QueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 临床路径方案DTO/BO组装服务
 * <p>
 * 负责将领域模型组装为DTO或BO对象，补充枚举名称、关联统计信息等。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CpPlanAssemblyService {

    private final CpComplianceRateMapper cpComplianceRateMapper;
    private final CpClinicalVisitMapper cpClinicalVisitMapper;
    private final CpDeviationService cpDeviationService;

    /**
     * 组装计划DTO对象
     */
    public CpPlanDto assemblePlanDto(CpPathwayPlan plan) {
        if (plan == null) {
            return null;
        }

        CpPlanDto dto = new CpPlanDto();
        BeanUtils.copyProperties(plan, dto);

        // 补充算法名称
        if (StringUtils.hasText(plan.getAlgorithmCode())) {
            AlgorithmEnum algorithm = AlgorithmEnum.fromCode(plan.getAlgorithmCode());
            if (algorithm != null) {
                dto.setAlgorithmName(algorithm.getName());
                dto.setAlgorithmDesc(algorithm.getDescription());
            }
        }

        // 补充正态转换名称
        if (StringUtils.hasText(plan.getNormalTransCode())) {
            NormalTransAlgorithmEnum transAlgo = NormalTransAlgorithmEnum.fromCode(plan.getNormalTransCode());
            if (transAlgo != null) {
                dto.setNormalTransName(transAlgo.getName());
            }
        }

        // 查询关联的路径依从率统计
        QueryWrapper avgQuery = QueryWrapper.create()
                .eq("plan_id", plan.getId())
                .orderBy("calc_date", false)
                .limit(1);
        CpComplianceRate latestAvg = cpComplianceRateMapper.selectOneByQuery(avgQuery);
        if (latestAvg != null) {
            dto.setLatestMean(latestAvg.getAvgMean());
            dto.setLatestSd(latestAvg.getAvgSd());
            dto.setLatestCv(latestAvg.getAvgCv());
            dto.setLatestCalcDate(latestAvg.getCalcDate());
        }

        // 查询最近的临床路径样本数
        QueryWrapper sampleCountQuery = QueryWrapper.create()
                .eq("plan_id", plan.getId())
                .eq("is_deleted", 0);
        long sampleCount = cpClinicalVisitMapper.selectCountByQuery(sampleCountQuery);
        dto.setSampleCount((int) sampleCount);

        // 查询最近的异常预警数
        int alarmCount = cpDeviationService.countRecentAlarms(plan.getId(), 7);
        dto.setRecentAlarmCount(alarmCount);

        return dto;
    }

    /**
     * 批量组装计划任务BO
     */
    public List<PlanTaskBo> assemblePlanTaskBos(List<String> planIds,
                                                 com.example.cp.mapper.CpPathwayPlanMapper cpPathwayPlanMapper) {
        if (CollectionUtils.isEmpty(planIds)) {
            return Collections.emptyList();
        }

        List<PlanTaskBo> taskBos = new ArrayList<>();
        for (String planId : planIds) {
            CpPathwayPlan plan = cpPathwayPlanMapper.selectOneById(planId);
            if (plan == null || plan.getIsDeleted() == 1) {
                continue;
            }

            PlanTaskBo taskBo = new PlanTaskBo();
            taskBo.setPlanId(plan.getId());
            taskBo.setLabCode(plan.getLabCode());
            taskBo.setInstrumentCode(plan.getInstrumentCode());
            taskBo.setItemCode(plan.getItemCode());
            taskBo.setAlgorithmCode(plan.getAlgorithmCode());
            taskBo.setMovingWindow(plan.getMovingWindow());
            taskBo.setTargetMean(plan.getTargetMean());
            taskBo.setTargetSd(plan.getTargetSd());
            taskBo.setControlLotNo(plan.getControlLotNo());
            taskBo.setControlLevel(plan.getControlLevel());
            taskBo.setNormalTransCode(plan.getNormalTransCode());
            taskBo.setTailProcessing(plan.getTailProcessing());
            taskBo.setExcludeWeekend(plan.getExcludeWeekend());
            taskBo.setTaskStatus("PENDING");
            taskBo.setCreateTime(LocalDateTime.now());

            taskBos.add(taskBo);
        }

        return taskBos;
    }
}
