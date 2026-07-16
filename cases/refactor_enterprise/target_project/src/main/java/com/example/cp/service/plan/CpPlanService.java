package com.example.cp.service.plan;

import com.example.cp.bo.task.PlanTaskBo;
import com.example.cp.dto.client.request.DataAnalysisRequestParamFactory;
import com.example.cp.dto.plan.CpPlanCreateRequest;
import com.example.cp.dto.plan.CpPlanDto;
import com.example.cp.dto.plan.CpPlanUpdateRequest;
import com.example.cp.dto.plan.CpPlanPageRequest;
import com.example.cp.dto.plan.CpPlanBatchRequest;
import com.example.cp.enums.plan.AlgorithmEnum;
import com.example.cp.enums.plan.NormalTransAlgorithmEnum;
import com.example.cp.enums.plan.TailProcessingEnum;
import com.example.cp.exception.CpBusinessException;
import com.example.cp.exception.CommonErrorCode;
import com.example.cp.mapper.CpPathwayPlanMapper;
import com.example.cp.mapper.CpPathwayVariationMapper;
import com.example.cp.mapper.CpComplianceRateMapper;
import com.example.cp.mapper.CpClinicalVisitMapper;
import com.example.cp.mapper.ck.BiTreatmentRecordMapper;
import com.example.cp.model.CpPathwayPlan;
import com.example.cp.model.CpPathwayVariation;
import com.example.cp.model.CpComplianceRate;
import com.example.cp.model.CpClinicalVisit;
import com.example.cp.model.ck.BiTreatmentRecord;
import com.example.cp.queue.RedisQueueService1;
import com.example.cp.service.monitor.CpDeviationService;

import com.mybatisflex.core.query.QueryWrapper;
import com.mybatisflex.core.paginate.Page;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.PostConstruct;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import jakarta.annotation.Resource;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

/**
 * 临床路径方案核心服务
 * <p>
 * 负责临床路径方案的全生命周期管理，包括：
 * - 临床路径方案的创建、修改、删除、查询
 * - 路径依从率算法的应用与参数校验
 * - 计划BO对象的组装与转换
 * - 计划变更记录的比对与审计
 * - 异步任务的调度与执行
 * </p>
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CpPlanService {

    // ========== 通过构造器注入的依赖 ==========
    private final CpPathwayPlanMapper cpPathwayPlanMapper;
    private final CpPathwayVariationMapper cpPathwayVariationMapper;
    private final CpComplianceRateMapper cpComplianceRateMapper;
    private final CpClinicalVisitMapper cpClinicalVisitMapper;
    private final BiTreatmentRecordMapper biInspectResultMapper;
    private final DataAnalysisRequestParamFactory dataAnalysisRequestParamFactory;

    // ========== 通过@Autowired注入的依赖（不一致的注入风格） ==========
    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    @Autowired
    private RedisQueueService1 redisQueueService;

    // ========== 通过@Resource注入的依赖（又一种不一致的注入风格） ==========
    @Resource
    private CpDeviationService cpDeviationService;

    @Resource(name = "cpTaskExecutor")
    private Executor cpTaskExecutor;

    // ========== 更多依赖注入 ==========
    @Autowired
    private com.example.cp.config.ThreadPoolConfig threadPoolConfig;

    @Resource
    private com.example.cp.config.RedisConfig redisConfig;

    @Autowired
    private com.example.cp.config.ClickHouseConfig clickHouseConfig;

    // ========== 硬编码的线程池（坏味道：应该使用Spring管理的Bean） ==========
    private static final ExecutorService PLAN_CALC_POOL = Executors.newFixedThreadPool(3);
    private static final ExecutorService CHANGE_DIFF_POOL = Executors.newFixedThreadPool(3);

    // ========== Magic String 常量（坏味道：应该提取到枚举或常量类） ==========
    private static final String PLAN_CACHE_PREFIX = "cp:plan:";
    private static final String PLAN_LOCK_PREFIX = "cp:plan:lock:";
    private static final String MOVING_AVG_KEY = "cp:pathway:avg:";
    private static final String DEFAULT_ALGORITHM = "WESTGARD";
    private static final int DEFAULT_MOVING_WINDOW = 20;
    private static final int MAX_RETRY_COUNT = 3;
    private static final String EXPORT_PATH = "D:/cp_data/export/";
    private static final String TEMP_FILE_PATH = "/tmp/cp/plan/";

    @Value("${cp.plan.max-items:500}")
    private Integer maxPlanItems;

    @Value("${cp.plan.cache-ttl:3600}")
    private Long cacheTtl;

    // ====================================================================
    //                         计划创建
    // ====================================================================

    /**
     * 创建临床路径方案
     * <p>
     * 校验参数合法性后创建计划，并初始化关联的路径依从率配置。
     * 创建成功后发送Redis消息通知偏差监测服务。
     * </p>
     *
     * @param request 创建请求
     * @return 计划DTO
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
        plan.setPlanStatus(1);  // 1=启用
        plan.setAlgorithmCode(algorithm.getCode());
        plan.setAlgorithmName(algorithm.getName());
        plan.setMovingWindow(request.getMovingWindow() != null ? request.getMovingWindow() : DEFAULT_MOVING_WINDOW);
        plan.setCreateTime(LocalDateTime.now());
        plan.setUpdateTime(LocalDateTime.now());
        plan.setCreator(request.getOperator());
        plan.setIsDeleted(0);

        // 设置正态转换算法（如果配置了）
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
            // 不影响主流程
        }

        // 清除缓存
        clearPlanCache(plan.getLabCode(), plan.getInstrumentCode());

        return assemblePlanDto(plan);
    }

    // ====================================================================
    //                         计划更新
    // ====================================================================

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

        // 记录变更前的快照（用于变更比对）
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

        // 异步记录变更差异
        CHANGE_DIFF_POOL.submit(() -> {
            try {
                recordPlanChange(snapshotBefore, existingPlan, request.getOperator());
            } catch (Exception e) {
                log.error("记录计划变更失败, planId={}", planId, e);
            }
        });

        // 清除缓存
        clearPlanCache(existingPlan.getLabCode(), existingPlan.getInstrumentCode());

        // 通知偏差监测服务刷新
        try {
            cpDeviationService.refreshPlanConfig(planId);
        } catch (Exception e) {
            log.error("通知偏差监测服务刷新失败, planId={}", planId, e);
        }

        return assemblePlanDto(existingPlan);
    }

    // ====================================================================
    //                         计划删除
    // ====================================================================

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
        clearPlanCache(plan.getLabCode(), plan.getInstrumentCode());
        redisTemplate.delete(PLAN_CACHE_PREFIX + planId);

        log.info("临床路径方案删除成功, planId={}", planId);
    }

    // ====================================================================
    //                         计划查询
    // ====================================================================

    /**
     * 根据ID查询计划详情
     */
    public CpPlanDto getPlanById(String planId) {
        // 先查缓存
        String cacheKey = PLAN_CACHE_PREFIX + planId;
        Object cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached instanceof CpPlanDto) {
            return (CpPlanDto) cached;
        }

        CpPathwayPlan plan = cpPathwayPlanMapper.selectOneById(planId);
        if (plan == null || plan.getIsDeleted() == 1) {
            throw new CpBusinessException(CommonErrorCode.PLAN_NOT_FOUND, "临床路径方案不存在: " + planId);
        }

        CpPlanDto dto = assemblePlanDto(plan);

        // 写入缓存
        redisTemplate.opsForValue().set(cacheKey, dto, cacheTtl, TimeUnit.SECONDS);

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

        // 转换为DTO
        List<CpPlanDto> dtoList = planPage.getRecords().stream()
                .map(this::assemblePlanDto)
                .collect(Collectors.toList());

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
        String cacheKey = PLAN_CACHE_PREFIX + "list:" + labCode + ":" + instrumentCode;
        Object cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached instanceof List) {
            return (List<CpPlanDto>) cached;
        }

        QueryWrapper query = QueryWrapper.create()
                .eq("lab_code", labCode)
                .eq("instrument_code", instrumentCode)
                .eq("is_deleted", 0)
                .orderBy("item_code", true);

        List<CpPathwayPlan> plans = cpPathwayPlanMapper.selectListByQuery(query);
        List<CpPlanDto> dtoList = plans.stream()
                .map(this::assemblePlanDto)
                .collect(Collectors.toList());

        redisTemplate.opsForValue().set(cacheKey, dtoList, cacheTtl, TimeUnit.SECONDS);
        return dtoList;
    }

    // ====================================================================
    //                         核心算法应用（坏味道：15参数方法）
    // ====================================================================

    /**
     * 应用临床路径路径依从率计划
     * <p>
     * 这是系统最核心的方法，负责将临床路径算法应用到指定的诊疗数据上。
     * 包括：数据采集、正态转换、路径依从率计算、规则判定、异常预警生成。
     * </p>
     *
     * 坏味道说明：参数过多（15个），应该封装为参数对象
     */
    @Transactional(rollbackFor = Exception.class)
    public Map<String, Object> applyCpPathwayPlan(
            String planId,
            String labCode,
            String instrumentCode,
            String itemCode,
            String controlLotNo,
            Integer controlLevel,
            String algorithmCode,
            Integer movingWindow,
            BigDecimal targetMean,
            BigDecimal targetSd,
            String normalTransCode,
            String tailProcessing,
            Boolean excludeWeekend,
            LocalDate startDate,
            LocalDate endDate) {

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
                labCode, instrumentCode, itemCode, controlLotNo,
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
        if (Boolean.TRUE.equals(excludeWeekend)) {
            filteredResults = rawResults.stream()
                    .filter(r -> {
                        if (r.getInspectTime() == null) return true;
                        int dayOfWeek = r.getInspectTime().toLocalDate().getDayOfWeek().getValue();
                        return dayOfWeek != 6 && dayOfWeek != 7;
                    })
                    .collect(Collectors.toList());
            log.info("排除周末后剩余 {} 条数据", filteredResults.size());
        }

        // 步骤3：正态转换
        List<BigDecimal> values = filteredResults.stream()
                .map(BiTreatmentRecord::getResultValue)
                .filter(Objects::nonNull)
                .collect(Collectors.toList());

        if (StringUtils.hasText(normalTransCode)) {
            values = applyNormalTransform(values, normalTransCode);
        }

        // 步骤4：计算路径依从率
        List<BigDecimal> movingAverages = calculateMovingAverage(values, movingWindow);

        // 步骤5：计算统计量
        BigDecimal calculatedMean = calculateMean(movingAverages);
        BigDecimal calculatedSd = calculateStandardDeviation(movingAverages, calculatedMean);
        BigDecimal calculatedCv = BigDecimal.ZERO;
        if (calculatedMean.compareTo(BigDecimal.ZERO) != 0) {
            calculatedCv = calculatedSd.divide(calculatedMean, 4, RoundingMode.HALF_UP)
                    .multiply(new BigDecimal("100"));
        }

        // 步骤6：尾数处理
        if (StringUtils.hasText(tailProcessing)) {
            TailProcessingEnum tailEnum = TailProcessingEnum.fromCode(tailProcessing);
            if (tailEnum != null) {
                int scale = tailEnum.getDecimalPlaces();
                calculatedMean = calculatedMean.setScale(scale, RoundingMode.HALF_UP);
                calculatedSd = calculatedSd.setScale(scale, RoundingMode.HALF_UP);
                calculatedCv = calculatedCv.setScale(scale, RoundingMode.HALF_UP);
            }
        }

        // 步骤7：应用Westgard规则判定
        AlgorithmEnum algorithm = AlgorithmEnum.fromCode(algorithmCode);
        BigDecimal finalMean = targetMean != null ? targetMean : calculatedMean;
        BigDecimal finalSd = targetSd != null ? targetSd : calculatedSd;
        List<Map<String, Object>> ruleViolations = applyWestgardRules(
                movingAverages, finalMean, finalSd, algorithm);

        // 步骤8：保存路径依从率记录
        saveMovingAvgRecords(planId, itemCode, instrumentCode, movingAverages,
                calculatedMean, calculatedSd, calculatedCv);

        // 步骤9：生成异常预警
        if (!CollectionUtils.isEmpty(ruleViolations)) {
            PLAN_CALC_POOL.submit(() -> {
                try {
                    cpDeviationService.generateAlarms(planId, ruleViolations);
                } catch (Exception e) {
                    log.error("生成异常预警失败, planId={}", planId, e);
                }
            });
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
        result.put("targetMean", targetMean);
        result.put("targetSd", targetSd);
        result.put("movingAverages", movingAverages);
        result.put("ruleViolations", ruleViolations);
        result.put("calcTime", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));

        log.info("临床路径路径依从率计划应用完成, planId={}, dataCount={}, violations={}",
                planId, filteredResults.size(), ruleViolations.size());

        return result;
    }

    // ====================================================================
    //                         BO对象组装
    // ====================================================================

    /**
     * 组装计划DTO对象
     */
    private CpPlanDto assemblePlanDto(CpPathwayPlan plan) {
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
    public List<PlanTaskBo> assemblePlanTaskBos(List<String> planIds) {
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

    // ====================================================================
    //                         变更比对
    // ====================================================================

    /**
     * 记录计划变更
     */
    private void recordPlanChange(CpPathwayPlan before, CpPathwayPlan after, String operator) {
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

    // ====================================================================
    //                         批量操作
    // ====================================================================

    /**
     * 批量启用/禁用计划
     */
    @Transactional(rollbackFor = Exception.class)
    public int batchUpdatePlanStatus(CpPlanBatchRequest request) {
        if (CollectionUtils.isEmpty(request.getPlanIds())) {
            return 0;
        }

        int count = 0;
        for (String planId : request.getPlanIds()) {
            CpPathwayPlan plan = cpPathwayPlanMapper.selectOneById(planId);
            if (plan != null && plan.getIsDeleted() == 0) {
                plan.setPlanStatus(request.getTargetStatus());
                plan.setUpdateTime(LocalDateTime.now());
                plan.setUpdater(request.getOperator());
                cpPathwayPlanMapper.update(plan);
                count++;

                // 清除单个计划缓存
                redisTemplate.delete(PLAN_CACHE_PREFIX + planId);
            }
        }

        log.info("批量更新计划状态完成, 目标状态={}, 成功数={}", request.getTargetStatus(), count);
        return count;
    }

    /**
     * 批量执行临床路径计算
     */
    public List<Map<String, Object>> batchExecutePlanCalc(List<String> planIds) {
        if (CollectionUtils.isEmpty(planIds)) {
            return Collections.emptyList();
        }

        List<Future<Map<String, Object>>> futures = new ArrayList<>();

        for (String planId : planIds) {
            Future<Map<String, Object>> future = PLAN_CALC_POOL.submit(() -> {
                try {
                    CpPathwayPlan plan = cpPathwayPlanMapper.selectOneById(planId);
                    if (plan == null || plan.getIsDeleted() == 1 || plan.getPlanStatus() != 1) {
                        Map<String, Object> skip = new HashMap<>();
                        skip.put("planId", planId);
                        skip.put("success", false);
                        skip.put("message", "计划不存在或已禁用");
                        return skip;
                    }

                    return applyCpPathwayPlan(
                            plan.getId(), plan.getLabCode(), plan.getInstrumentCode(),
                            plan.getItemCode(), plan.getControlLotNo(), plan.getControlLevel(),
                            plan.getAlgorithmCode(), plan.getMovingWindow(),
                            plan.getTargetMean(), plan.getTargetSd(),
                            plan.getNormalTransCode(), plan.getTailProcessing(),
                            plan.getExcludeWeekend(),
                            LocalDate.now().minusDays(30), LocalDate.now());
                } catch (Exception e) {
                    log.error("批量计算失败, planId={}", planId, e);
                    Map<String, Object> error = new HashMap<>();
                    error.put("planId", planId);
                    error.put("success", false);
                    error.put("message", e.getMessage());
                    return error;
                }
            });
            futures.add(future);
        }

        List<Map<String, Object>> results = new ArrayList<>();
        for (Future<Map<String, Object>> future : futures) {
            try {
                results.add(future.get(60, TimeUnit.SECONDS));
            } catch (Exception e) {
                Map<String, Object> timeout = new HashMap<>();
                timeout.put("success", false);
                timeout.put("message", "计算超时");
                results.add(timeout);
            }
        }

        return results;
    }

    // ====================================================================
    //   注释掉的代码块（坏味道：废弃的旧版重构代码没有清理）
    // ====================================================================

    // TODO: 以下代码为旧版临床路径方案导出逻辑，已在v2.3.0中重构到DataExportService
    // 暂时保留以防回滚需要 —— @zhangsan 2024-01-15
    //
    // public void exportPlanDataToExcel(String planId, String outputPath) {
    //     CpPathwayPlan plan = cpPathwayPlanMapper.selectOneById(planId);
    //     if (plan == null) {
    //         throw new CpBusinessException(CommonErrorCode.PLAN_NOT_FOUND, "计划不存在");
    //     }
    //     QueryWrapper query = QueryWrapper.create()
    //             .eq("plan_id", planId)
    //             .orderBy("calc_date", true);
    //     List<CpComplianceRate> avgList = cpComplianceRateMapper.selectListByQuery(query);
    //
    //     // 使用EasyExcel导出
    //     String filePath = EXPORT_PATH + plan.getItemCode() + "_" +
    //             LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd")) + ".xlsx";
    //     // EasyExcel.write(filePath, CpPlanExportVo.class)
    //     //         .sheet("临床路径数据")
    //     //         .doWrite(convertToExportVo(avgList));
    //     //
    //     // // 上传到文件服务器
    //     // FileUploadResult uploadResult = fileService.upload(filePath);
    //     // log.info("临床路径方案数据导出成功, planId={}, fileUrl={}", planId, uploadResult.getUrl());
    //     //
    //     // // 清理临时文件
    //     // FileUtils.deleteQuietly(new File(filePath));
    //     //
    //     // return uploadResult.getUrl();
    // }

    // ====================================================================
    //                         内部计算方法
    // ====================================================================

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

    /**
     * 计算移动平均值
     */
    private List<BigDecimal> calculateMovingAverage(List<BigDecimal> values, int window) {
        if (values == null || values.size() < window) {
            return values != null ? values : Collections.emptyList();
        }

        List<BigDecimal> movingAvgs = new ArrayList<>();
        for (int i = 0; i <= values.size() - window; i++) {
            BigDecimal sum = BigDecimal.ZERO;
            for (int j = i; j < i + window; j++) {
                sum = sum.add(values.get(j));
            }
            BigDecimal avg = sum.divide(new BigDecimal(window), 6, RoundingMode.HALF_UP);
            movingAvgs.add(avg);
        }
        return movingAvgs;
    }

    /**
     * 计算均值
     */
    private BigDecimal calculateMean(List<BigDecimal> values) {
        if (CollectionUtils.isEmpty(values)) {
            return BigDecimal.ZERO;
        }
        BigDecimal sum = values.stream().reduce(BigDecimal.ZERO, BigDecimal::add);
        return sum.divide(new BigDecimal(values.size()), 6, RoundingMode.HALF_UP);
    }

    /**
     * 计算标准差
     */
    private BigDecimal calculateStandardDeviation(List<BigDecimal> values, BigDecimal mean) {
        if (CollectionUtils.isEmpty(values) || values.size() < 2) {
            return BigDecimal.ZERO;
        }

        BigDecimal sumOfSquares = BigDecimal.ZERO;
        for (BigDecimal value : values) {
            BigDecimal diff = value.subtract(mean);
            sumOfSquares = sumOfSquares.add(diff.multiply(diff));
        }

        BigDecimal variance = sumOfSquares.divide(
                new BigDecimal(values.size() - 1), 10, RoundingMode.HALF_UP);

        // 使用牛顿法开方
        return sqrt(variance, 6);
    }

    /**
     * BigDecimal开方（牛顿迭代法）
     */
    private BigDecimal sqrt(BigDecimal value, int scale) {
        if (value.compareTo(BigDecimal.ZERO) <= 0) {
            return BigDecimal.ZERO;
        }

        BigDecimal two = new BigDecimal("2");
        BigDecimal x0 = new BigDecimal(Math.sqrt(value.doubleValue()));
        BigDecimal x1;

        for (int i = 0; i < 20; i++) {
            x1 = value.divide(x0, scale + 2, RoundingMode.HALF_UP);
            x1 = x1.add(x0);
            x1 = x1.divide(two, scale + 2, RoundingMode.HALF_UP);
            if (x0.compareTo(x1) == 0) break;
            x0 = x1;
        }

        return x0.setScale(scale, RoundingMode.HALF_UP);
    }

    /**
     * 应用正态转换
     */
    private List<BigDecimal> applyNormalTransform(List<BigDecimal> values, String transCode) {
        NormalTransAlgorithmEnum transAlgo = NormalTransAlgorithmEnum.fromCode(transCode);
        if (transAlgo == null) {
            return values;
        }

        switch (transAlgo) {
            case LOG_TRANSFORM:
                return values.stream()
                        .map(v -> {
                            if (v.compareTo(BigDecimal.ZERO) <= 0) return v;
                            return new BigDecimal(Math.log(v.doubleValue()))
                                    .setScale(6, RoundingMode.HALF_UP);
                        })
                        .collect(Collectors.toList());

            case SQRT_TRANSFORM:
                return values.stream()
                        .map(v -> {
                            if (v.compareTo(BigDecimal.ZERO) < 0) return v;
                            return new BigDecimal(Math.sqrt(v.doubleValue()))
                                    .setScale(6, RoundingMode.HALF_UP);
                        })
                        .collect(Collectors.toList());

            case BOX_COX:
                // Box-Cox变换简化实现（lambda=0.5）
                return values.stream()
                        .map(v -> {
                            if (v.compareTo(BigDecimal.ZERO) <= 0) return v;
                            double lambda = 0.5;
                            double transformed = (Math.pow(v.doubleValue(), lambda) - 1) / lambda;
                            return new BigDecimal(transformed).setScale(6, RoundingMode.HALF_UP);
                        })
                        .collect(Collectors.toList());

            default:
                return values;
        }
    }

    /**
     * 应用Westgard临床路径规则
     */
    private List<Map<String, Object>> applyWestgardRules(
            List<BigDecimal> values, BigDecimal mean, BigDecimal sd, AlgorithmEnum algorithm) {

        List<Map<String, Object>> violations = new ArrayList<>();
        if (CollectionUtils.isEmpty(values) || sd.compareTo(BigDecimal.ZERO) == 0) {
            return violations;
        }

        BigDecimal twoSd = sd.multiply(new BigDecimal("2"));
        BigDecimal threeSd = sd.multiply(new BigDecimal("3"));

        for (int i = 0; i < values.size(); i++) {
            BigDecimal value = values.get(i);
            BigDecimal deviation = value.subtract(mean).abs();

            // 1-3s规则：单个值超过±3SD
            if (deviation.compareTo(threeSd) > 0) {
                Map<String, Object> v = new HashMap<>();
                v.put("ruleCode", "1-3s");
                v.put("ruleName", "单值超过3个标准差");
                v.put("index", i);
                v.put("value", value);
                v.put("deviation", deviation);
                v.put("level", "CRITICAL");
                violations.add(v);
            }

            // 1-2s规则：单个值超过±2SD（警告）
            if (deviation.compareTo(twoSd) > 0 && deviation.compareTo(threeSd) <= 0) {
                Map<String, Object> v = new HashMap<>();
                v.put("ruleCode", "1-2s");
                v.put("ruleName", "单值超过2个标准差");
                v.put("index", i);
                v.put("value", value);
                v.put("deviation", deviation);
                v.put("level", "WARNING");
                violations.add(v);
            }

            // 2-2s规则：连续2个值超过同侧±2SD
            if (i > 0) {
                BigDecimal prevValue = values.get(i - 1);
                BigDecimal prevDev = prevValue.subtract(mean);
                BigDecimal currDev = value.subtract(mean);

                if (prevDev.abs().compareTo(twoSd) > 0 && currDev.abs().compareTo(twoSd) > 0
                        && prevDev.signum() == currDev.signum()) {
                    Map<String, Object> v = new HashMap<>();
                    v.put("ruleCode", "2-2s");
                    v.put("ruleName", "连续2值同侧超过2个标准差");
                    v.put("index", i);
                    v.put("value", value);
                    v.put("level", "ERROR");
                    violations.add(v);
                }
            }

            // R-4s规则：连续2个值之差超过4SD
            if (i > 0) {
                BigDecimal prevValue = values.get(i - 1);
                BigDecimal range = value.subtract(prevValue).abs();
                BigDecimal fourSd = sd.multiply(new BigDecimal("4"));
                if (range.compareTo(fourSd) > 0) {
                    Map<String, Object> v = new HashMap<>();
                    v.put("ruleCode", "R-4s");
                    v.put("ruleName", "连续2值之差超过4个标准差");
                    v.put("index", i);
                    v.put("value", value);
                    v.put("level", "ERROR");
                    violations.add(v);
                }
            }

            // 10x规则：连续10个值在均值同侧
            if (i >= 9) {
                boolean allSameSide = true;
                int firstSign = values.get(i - 9).subtract(mean).signum();
                if (firstSign == 0) firstSign = 1;
                for (int k = i - 8; k <= i; k++) {
                    int sign = values.get(k).subtract(mean).signum();
                    if (sign == 0) sign = 1;
                    if (sign != firstSign) {
                        allSameSide = false;
                        break;
                    }
                }
                if (allSameSide) {
                    Map<String, Object> v = new HashMap<>();
                    v.put("ruleCode", "10x");
                    v.put("ruleName", "连续10值在均值同侧");
                    v.put("index", i);
                    v.put("value", value);
                    v.put("level", "WARNING");
                    violations.add(v);
                }
            }
        }

        return violations;
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

    /**
     * 清除计划缓存
     */
    private void clearPlanCache(String labCode, String instrumentCode) {
        try {
            String listCacheKey = PLAN_CACHE_PREFIX + "list:" + labCode + ":" + instrumentCode;
            redisTemplate.delete(listCacheKey);
        } catch (Exception e) {
            log.warn("清除计划列表缓存失败, labCode={}, instrumentCode={}", labCode, instrumentCode, e);
        }
    }

    // ====================================================================
    //                         辅助查询方法
    // ====================================================================

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

    @PostConstruct
    public void init() {
        log.info("CpPlanService 初始化完成, maxPlanItems={}, cacheTtl={}", maxPlanItems, cacheTtl);
    }
}
