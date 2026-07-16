package com.example.cp.service.plan;

import com.example.cp.dto.plan.CpPlanCreateRequest;
import com.example.cp.dto.plan.CpPlanDto;
import com.example.cp.dto.plan.CpPlanPageRequest;
import com.example.cp.dto.plan.CpPlanUpdateRequest;
import com.example.cp.enums.plan.AlgorithmEnum;
import com.example.cp.enums.plan.NormalTransAlgorithmEnum;
import com.example.cp.enums.plan.TailProcessingEnum;
import com.example.cp.exception.CpBusinessException;
import com.example.cp.exception.CommonErrorCode;
import com.example.cp.mapper.CpPathwayPlanMapper;
import com.example.cp.mapper.CpComplianceRateMapper;
import com.example.cp.model.CpPathwayPlan;
import com.example.cp.model.CpComplianceRate;
import com.example.cp.queue.RedisQueueService1;
import com.example.cp.service.monitor.CpDeviationService;

import com.mybatisflex.core.query.QueryWrapper;
import com.mybatisflex.core.paginate.Page;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

/**
 * 临床路径方案CRUD服务
 * <p>
 * 负责临床路径方案的创建、更新、删除、查询等基本生命周期管理。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CpPlanCrudService {

    private final CpPathwayPlanMapper cpPathwayPlanMapper;
    private final CpComplianceRateMapper cpComplianceRateMapper;
    private final CpPlanAssemblyService cpPlanAssemblyService;
    private final CpPlanCacheService cpPlanCacheService;
    private final CpPlanChangeService cpPlanChangeService;
    private final CpDeviationService cpDeviationService;
    private final RedisQueueService1 redisQueueService;

    private static final int DEFAULT_MOVING_WINDOW = 20;

    /**
     * 创建临床路径方案
     */
    @Transactional(rollbackFor = Exception.class)
    public CpPlanDto createPlan(@Valid CpPlanCreateRequest request) {
        log.info("开始创建临床路径方案, 项目编码={}, 科室编码={}", request.getItemCode(), request.getInstrumentCode());

        // 校验是否存在重复计划
        QueryWrapper existQuery = QueryWrapper.create()
                .eq("item_code", request.getItemCode())
                .eq("instrument_code", request.getInstrumentCode())
                .eq("lab_code", request.getLabCode())
                .eq("is_deleted", 0);
        long existCount = cpPathwayPlanMapper.selectCountByQuery(existQuery);
        if (existCount > 0) {
            throw new CpBusinessException(CommonErrorCode.DUPLICATE_PLAN,
                    "该项目在该科室上已存在临床路径方案: " + request.getItemCode());
        }

        // 校验算法参数
        AlgorithmEnum algorithm = AlgorithmEnum.fromCode(request.getAlgorithmCode());
        if (algorithm == null) {
            throw new CpBusinessException(CommonErrorCode.INVALID_PARAM, "不支持的算法编码: " + request.getAlgorithmCode());
        }

        // 校验尾数处理方式
        if (request.getTailProcessing() != null) {
            TailProcessingEnum tailEnum = TailProcessingEnum.fromCode(request.getTailProcessing());
            if (tailEnum == null) {
                log.warn("无效的尾数处理方式: {}, 将使用默认值", request.getTailProcessing());
            }
        }

        // 构建实体
        CpPathwayPlan plan = new CpPathwayPlan();
        BeanUtils.copyProperties(request, plan);
        plan.setId(UUID.randomUUID().toString().replace("-", ""));
        plan.setPlanStatus(1);
        plan.setAlgorithmCode(algorithm.getCode());
        plan.setAlgorithmName(algorithm.getName());
        plan.setMovingWindow(request.getMovingWindow() != null ? request.getMovingWindow() : DEFAULT_MOVING_WINDOW);
        plan.setCreateTime(LocalDateTime.now());
        plan.setUpdateTime(LocalDateTime.now());
        plan.setCreator(request.getOperator());
        plan.setIsDeleted(0);

        // 设置正态转换算法
        if (StringUtils.hasText(request.getNormalTransCode())) {
            NormalTransAlgorithmEnum transAlgo = NormalTransAlgorithmEnum.fromCode(request.getNormalTransCode());
            if (transAlgo != null) {
                plan.setNormalTransCode(transAlgo.getCode());
                plan.setNormalTransName(transAlgo.getName());
            }
        }

        cpPathwayPlanMapper.insert(plan);
        log.info("临床路径方案创建成功, planId={}", plan.getId());

        // 初始化路径依从率记录
        initMovingAvgRecords(plan);

        // 发送创建事件到Redis队列
        try {
            Map<String, Object> event = new HashMap<>();
            event.put("type", "PLAN_CREATED");
            event.put("planId", plan.getId());
            event.put("itemCode", plan.getItemCode());
            event.put("timestamp", System.currentTimeMillis());
            redisQueueService.sendMessage("cp:event:plan", event);
        } catch (Exception e) {
            log.error("发送计划创建事件失败, planId={}", plan.getId(), e);
        }

        // 清除缓存
        cpPlanCacheService.clearPlanListCache(plan.getLabCode(), plan.getInstrumentCode());

        return cpPlanAssemblyService.assemblePlanDto(plan);
    }

    /**
     * 更新临床路径方案
     */
    @Transactional(rollbackFor = Exception.class)
    public CpPlanDto updatePlan(String planId, @Valid CpPlanUpdateRequest request) {
        log.info("开始更新临床路径方案, planId={}", planId);

        CpPathwayPlan existingPlan = cpPathwayPlanMapper.selectOneById(planId);
        if (existingPlan == null || existingPlan.getIsDeleted() == 1) {
            throw new CpBusinessException(CommonErrorCode.PLAN_NOT_FOUND, "临床路径方案不存在: " + planId);
        }

        // 记录变更前的快照
        CpPathwayPlan snapshotBefore = new CpPathwayPlan();
        BeanUtils.copyProperties(existingPlan, snapshotBefore);

        // 更新字段
        if (StringUtils.hasText(request.getAlgorithmCode())) {
            AlgorithmEnum algorithm = AlgorithmEnum.fromCode(request.getAlgorithmCode());
            if (algorithm == null) {
                throw new CpBusinessException(CommonErrorCode.INVALID_PARAM, "不支持的算法编码");
            }
            existingPlan.setAlgorithmCode(algorithm.getCode());
            existingPlan.setAlgorithmName(algorithm.getName());
        }

        if (request.getMovingWindow() != null) {
            if (request.getMovingWindow() < 5 || request.getMovingWindow() > 100) {
                throw new CpBusinessException(CommonErrorCode.INVALID_PARAM,
                        "移动窗口大小必须在5-100之间, 当前值: " + request.getMovingWindow());
            }
            existingPlan.setMovingWindow(request.getMovingWindow());
        }

        if (request.getTargetMean() != null) {
            existingPlan.setTargetMean(request.getTargetMean());
        }
        if (request.getTargetSd() != null) {
            existingPlan.setTargetSd(request.getTargetSd());
        }
        if (request.getTargetCv() != null) {
            existingPlan.setTargetCv(request.getTargetCv());
        }
        if (request.getControlLotNo() != null) {
            existingPlan.setControlLotNo(request.getControlLotNo());
        }
        if (request.getControlLevel() != null) {
            existingPlan.setControlLevel(request.getControlLevel());
        }
        if (request.getPlanStatus() != null) {
            existingPlan.setPlanStatus(request.getPlanStatus());
        }
        if (request.getExcludeWeekend() != null) {
            existingPlan.setExcludeWeekend(request.getExcludeWeekend());
        }
        if (request.getNormalTransCode() != null) {
            NormalTransAlgorithmEnum transAlgo = NormalTransAlgorithmEnum.fromCode(request.getNormalTransCode());
            if (transAlgo != null) {
                existingPlan.setNormalTransCode(transAlgo.getCode());
                existingPlan.setNormalTransName(transAlgo.getName());
            }
        }

        existingPlan.setUpdateTime(LocalDateTime.now());
        existingPlan.setUpdater(request.getOperator());

        cpPathwayPlanMapper.update(existingPlan);
        log.info("临床路径方案更新成功, planId={}", planId);

        // 记录变更差异
        cpPlanChangeService.recordPlanChange(snapshotBefore, existingPlan, request.getOperator());

        // 清除缓存
        cpPlanCacheService.clearPlanListCache(existingPlan.getLabCode(), existingPlan.getInstrumentCode());

        // 通知偏差监测服务刷新
        try {
            cpDeviationService.refreshPlanConfig(planId);
        } catch (Exception e) {
            log.error("通知偏差监测服务刷新失败, planId={}", planId, e);
        }

        return cpPlanAssemblyService.assemblePlanDto(existingPlan);
    }

    /**
     * 逻辑删除临床路径方案
     */
    @Transactional(rollbackFor = Exception.class)
    public void deletePlan(String planId, String operator) {
        log.info("开始删除临床路径方案, planId={}, operator={}", planId, operator);

        CpPathwayPlan plan = cpPathwayPlanMapper.selectOneById(planId);
        if (plan == null) {
            throw new CpBusinessException(CommonErrorCode.PLAN_NOT_FOUND, "临床路径方案不存在");
        }

        // 检查是否有正在运行的偏差监测任务
        boolean hasRunningTask = cpDeviationService.hasRunningTask(planId);
        if (hasRunningTask) {
            throw new CpBusinessException(CommonErrorCode.PLAN_IN_USE,
                    "该计划存在正在运行的偏差监测任务，无法删除");
        }

        plan.setIsDeleted(1);
        plan.setUpdateTime(LocalDateTime.now());
        plan.setUpdater(operator);
        cpPathwayPlanMapper.update(plan);

        // 同时删除关联的路径依从率记录
        QueryWrapper avgDeleteQuery = QueryWrapper.create()
                .eq("plan_id", planId);
        cpComplianceRateMapper.deleteByQuery(avgDeleteQuery);

        // 清除缓存
        cpPlanCacheService.clearPlanListCache(plan.getLabCode(), plan.getInstrumentCode());
        cpPlanCacheService.clearPlanCache(planId);

        log.info("临床路径方案删除成功, planId={}", planId);
    }

    /**
     * 根据ID查询计划详情
     */
    public CpPlanDto getPlanById(String planId) {
        // 先查缓存
        CpPlanDto cached = cpPlanCacheService.get(planId);
        if (cached != null) {
            return cached;
        }

        CpPathwayPlan plan = cpPathwayPlanMapper.selectOneById(planId);
        if (plan == null || plan.getIsDeleted() == 1) {
            throw new CpBusinessException(CommonErrorCode.PLAN_NOT_FOUND, "临床路径方案不存在: " + planId);
        }

        CpPlanDto dto = cpPlanAssemblyService.assemblePlanDto(plan);

        // 写入缓存
        cpPlanCacheService.set(planId, dto, 3600);

        return dto;
    }

    /**
     * 分页查询临床路径方案列表
     */
    public Page<CpPlanDto> queryPlanPage(CpPlanPageRequest request) {
        log.debug("分页查询临床路径方案, labCode={}, page={}, size={}",
                request.getLabCode(), request.getPageNum(), request.getPageSize());

        QueryWrapper query = QueryWrapper.create()
                .eq("is_deleted", 0);

        if (StringUtils.hasText(request.getLabCode())) {
            query.eq("lab_code", request.getLabCode());
        }
        if (StringUtils.hasText(request.getInstrumentCode())) {
            query.eq("instrument_code", request.getInstrumentCode());
        }
        if (StringUtils.hasText(request.getItemCode())) {
            query.like("item_code", request.getItemCode());
        }
        if (request.getPlanStatus() != null) {
            query.eq("plan_status", request.getPlanStatus());
        }
        if (StringUtils.hasText(request.getAlgorithmCode())) {
            query.eq("algorithm_code", request.getAlgorithmCode());
        }
        if (request.getStartDate() != null) {
            query.ge("create_time", request.getStartDate().atStartOfDay());
        }
        if (request.getEndDate() != null) {
            query.le("create_time", request.getEndDate().atTime(23, 59, 59));
        }

        query.orderBy("create_time", false);

        Page<CpPathwayPlan> planPage = cpPathwayPlanMapper.paginate(
                Page.of(request.getPageNum(), request.getPageSize()), query);

        List<CpPlanDto> dtoList = planPage.getRecords().stream()
                .map(cpPlanAssemblyService::assemblePlanDto)
                .toList();

        Page<CpPlanDto> resultPage = new Page<>();
        resultPage.setRecords(dtoList);
        resultPage.setPageNumber(planPage.getPageNumber());
        resultPage.setPageSize(planPage.getPageSize());
        resultPage.setTotalRow(planPage.getTotalRow());

        return resultPage;
    }

    /**
     * 根据实验室和科室查询计划列表
     */
    public List<CpPlanDto> queryPlansByLabAndInstrument(String labCode, String instrumentCode) {
        String cacheKey = "list:" + labCode + ":" + instrumentCode;
        List<CpPlanDto> cached = cpPlanCacheService.get(cacheKey);
        if (cached != null) {
            return cached;
        }

        QueryWrapper query = QueryWrapper.create()
                .eq("lab_code", labCode)
                .eq("instrument_code", instrumentCode)
                .eq("is_deleted", 0)
                .orderBy("item_code", true);

        List<CpPathwayPlan> plans = cpPathwayPlanMapper.selectListByQuery(query);
        List<CpPlanDto> dtoList = plans.stream()
                .map(cpPlanAssemblyService::assemblePlanDto)
                .toList();

        cpPlanCacheService.set(cacheKey, dtoList, 3600);
        return dtoList;
    }

    /**
     * 统计各状态的计划数量
     */
    public Map<String, Long> countPlanByStatus(String labCode) {
        Map<String, Long> result = new LinkedHashMap<>();

        QueryWrapper activeQuery = QueryWrapper.create()
                .eq("lab_code", labCode)
                .eq("plan_status", 1)
                .eq("is_deleted", 0);
        result.put("active", cpPathwayPlanMapper.selectCountByQuery(activeQuery));

        QueryWrapper disabledQuery = QueryWrapper.create()
                .eq("lab_code", labCode)
                .eq("plan_status", 0)
                .eq("is_deleted", 0);
        result.put("disabled", cpPathwayPlanMapper.selectCountByQuery(disabledQuery));

        QueryWrapper totalQuery = QueryWrapper.create()
                .eq("lab_code", labCode)
                .eq("is_deleted", 0);
        result.put("total", cpPathwayPlanMapper.selectCountByQuery(totalQuery));

        return result;
    }

    /**
     * 获取需要执行计算的计划列表（供定时任务调用）
     */
    public List<CpPathwayPlan> getPlansNeedingCalc(String labCode) {
        QueryWrapper query = QueryWrapper.create()
                .eq("lab_code", labCode)
                .eq("plan_status", 1)
                .eq("is_deleted", 0)
                .and(new com.mybatisflex.core.query.QueryColumn("last_calc_time").isNull(true)
                        .or(new com.mybatisflex.core.query.QueryColumn("last_calc_time").le(LocalDateTime.now().minusHours(1))));

        return cpPathwayPlanMapper.selectListByQuery(query);
    }

    /**
     * 初始化路径依从率记录
     */
    private void initMovingAvgRecords(CpPathwayPlan plan) {
        CpComplianceRate avg = new CpComplianceRate();
        avg.setId(UUID.randomUUID().toString().replace("-", ""));
        avg.setPlanId(plan.getId());
        avg.setItemCode(plan.getItemCode());
        avg.setInstrumentCode(plan.getInstrumentCode());
        avg.setAvgMean(BigDecimal.ZERO);
        avg.setAvgSd(BigDecimal.ZERO);
        avg.setAvgCv(BigDecimal.ZERO);
        avg.setDataCount(0);
        avg.setCalcDate(LocalDate.now());
        avg.setCreateTime(LocalDateTime.now());
        cpComplianceRateMapper.insert(avg);
    }
}
