package com.example.cp.service.plan;

import com.example.cp.mapper.CpPathwayVariationMapper;
import com.example.cp.model.CpPathwayPlan;
import com.example.cp.model.CpPathwayVariation;

import com.mybatisflex.core.query.QueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

/**
 * 临床路径方案变更追踪服务
 * <p>
 * 负责记录和查询临床路径方案配置的变更历史。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CpPlanChangeService {

    private final CpPathwayVariationMapper cpPathwayVariationMapper;

    /**
     * 记录计划变更
     */
    public void recordPlanChange(CpPathwayPlan before, CpPathwayPlan after, String operator) {
        List<CpPathwayVariation> changes = new ArrayList<>();

        // 逐字段比对
        if (!Objects.equals(before.getAlgorithmCode(), after.getAlgorithmCode())) {
            changes.add(buildChange(after.getId(), "algorithm_code",
                    before.getAlgorithmCode(), after.getAlgorithmCode(), operator));
        }
        if (!Objects.equals(before.getMovingWindow(), after.getMovingWindow())) {
            changes.add(buildChange(after.getId(), "moving_window",
                    String.valueOf(before.getMovingWindow()), String.valueOf(after.getMovingWindow()), operator));
        }
        if (!Objects.equals(before.getTargetMean(), after.getTargetMean())) {
            changes.add(buildChange(after.getId(), "target_mean",
                    before.getTargetMean() != null ? before.getTargetMean().toPlainString() : "",
                    after.getTargetMean() != null ? after.getTargetMean().toPlainString() : "", operator));
        }
        if (!Objects.equals(before.getTargetSd(), after.getTargetSd())) {
            changes.add(buildChange(after.getId(), "target_sd",
                    before.getTargetSd() != null ? before.getTargetSd().toPlainString() : "",
                    after.getTargetSd() != null ? after.getTargetSd().toPlainString() : "", operator));
        }
        if (!Objects.equals(before.getTargetCv(), after.getTargetCv())) {
            changes.add(buildChange(after.getId(), "target_cv",
                    before.getTargetCv() != null ? before.getTargetCv().toPlainString() : "",
                    after.getTargetCv() != null ? after.getTargetCv().toPlainString() : "", operator));
        }
        if (!Objects.equals(before.getControlLotNo(), after.getControlLotNo())) {
            changes.add(buildChange(after.getId(), "control_lot_no",
                    before.getControlLotNo(), after.getControlLotNo(), operator));
        }
        if (!Objects.equals(before.getControlLevel(), after.getControlLevel())) {
            changes.add(buildChange(after.getId(), "control_level",
                    String.valueOf(before.getControlLevel()), String.valueOf(after.getControlLevel()), operator));
        }
        if (!Objects.equals(before.getPlanStatus(), after.getPlanStatus())) {
            changes.add(buildChange(after.getId(), "plan_status",
                    String.valueOf(before.getPlanStatus()), String.valueOf(after.getPlanStatus()), operator));
        }
        if (!Objects.equals(before.getNormalTransCode(), after.getNormalTransCode())) {
            changes.add(buildChange(after.getId(), "normal_trans_code",
                    before.getNormalTransCode(), after.getNormalTransCode(), operator));
        }
        if (!Objects.equals(before.getExcludeWeekend(), after.getExcludeWeekend())) {
            changes.add(buildChange(after.getId(), "exclude_weekend",
                    String.valueOf(before.getExcludeWeekend()), String.valueOf(after.getExcludeWeekend()), operator));
        }

        if (!changes.isEmpty()) {
            for (CpPathwayVariation change : changes) {
                cpPathwayVariationMapper.insert(change);
            }
            log.info("记录计划变更 {} 条, planId={}", changes.size(), after.getId());
        }
    }

    /**
     * 查询计划变更历史
     */
    public List<CpPathwayVariation> queryPlanChanges(String planId, LocalDate startDate, LocalDate endDate) {
        QueryWrapper query = QueryWrapper.create()
                .eq("plan_id", planId);

        if (startDate != null) {
            query.ge("change_time", startDate.atStartOfDay());
        }
        if (endDate != null) {
            query.le("change_time", endDate.atTime(23, 59, 59));
        }
        query.orderBy("change_time", false);

        return cpPathwayVariationMapper.selectListByQuery(query);
    }

    private CpPathwayVariation buildChange(String planId, String fieldName,
                                           String oldValue, String newValue, String operator) {
        CpPathwayVariation change = new CpPathwayVariation();
        change.setId(UUID.randomUUID().toString().replace("-", ""));
        change.setPlanId(planId);
        change.setFieldName(fieldName);
        change.setOldValue(oldValue);
        change.setNewValue(newValue);
        change.setOperator(operator);
        change.setChangeTime(LocalDateTime.now());
        return change;
    }
}
