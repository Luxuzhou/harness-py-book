package com.example.cp.service.plan;

import com.example.cp.dto.plan.CpPlanBatchRequest;
import com.example.cp.mapper.CpPathwayPlanMapper;
import com.example.cp.model.CpPathwayPlan;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * CpPlanBatchService 单元测试
 */
@ExtendWith(MockitoExtension.class)
class CpPlanBatchServiceTest {

    @Mock
    private CpPathwayPlanMapper cpPathwayPlanMapper;
    @Mock
    private CpPlanCacheService cpPlanCacheService;
    @Mock
    private CpPlanCalculationService cpPlanCalculationService;

    private CpPlanBatchService cpPlanBatchService;

    @BeforeEach
    void setUp() {
        cpPlanBatchService = new CpPlanBatchService(
                cpPathwayPlanMapper, cpPlanCacheService, cpPlanCalculationService);
    }

    @Test
    void testBatchUpdatePlanStatus_success() {
        CpPlanBatchRequest request = new CpPlanBatchRequest();
        request.setPlanIds(Arrays.asList("plan-1", "plan-2"));
        request.setTargetStatus(0);
        request.setOperator("admin");

        CpPathwayPlan plan1 = new CpPathwayPlan();
        plan1.setId("plan-1");
        plan1.setIsDeleted(0);

        CpPathwayPlan plan2 = new CpPathwayPlan();
        plan2.setId("plan-2");
        plan2.setIsDeleted(0);

        when(cpPathwayPlanMapper.selectOneById("plan-1")).thenReturn(plan1);
        when(cpPathwayPlanMapper.selectOneById("plan-2")).thenReturn(plan2);

        int count = cpPlanBatchService.batchUpdatePlanStatus(request);
        assertEquals(2, count);
        verify(cpPathwayPlanMapper, times(2)).update(any(CpPathwayPlan.class));
        verify(cpPlanCacheService, times(2)).clearPlanCache(anyString());
    }

    @Test
    void testBatchUpdatePlanStatus_emptyIds() {
        CpPlanBatchRequest request = new CpPlanBatchRequest();
        request.setPlanIds(Collections.emptyList());

        int count = cpPlanBatchService.batchUpdatePlanStatus(request);
        assertEquals(0, count);
        verify(cpPathwayPlanMapper, never()).update(any());
    }

    @Test
    void testBatchUpdatePlanStatus_planNotFound() {
        CpPlanBatchRequest request = new CpPlanBatchRequest();
        request.setPlanIds(Arrays.asList("plan-1", "plan-999"));
        request.setTargetStatus(0);
        request.setOperator("admin");

        CpPathwayPlan plan1 = new CpPathwayPlan();
        plan1.setId("plan-1");
        plan1.setIsDeleted(0);

        when(cpPathwayPlanMapper.selectOneById("plan-1")).thenReturn(plan1);
        when(cpPathwayPlanMapper.selectOneById("plan-999")).thenReturn(null);

        int count = cpPlanBatchService.batchUpdatePlanStatus(request);
        assertEquals(1, count);
    }

    @Test
    void testBatchExecutePlanCalc_emptyIds() {
        List<Map<String, Object>> results = cpPlanBatchService.batchExecutePlanCalc(Collections.emptyList());
        assertTrue(results.isEmpty());
    }
}
