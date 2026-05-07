package com.example.cp.service.plan;

import com.example.cp.dto.plan.CpPlanCreateRequest;
import com.example.cp.dto.plan.CpPlanDto;
import com.example.cp.dto.plan.CpPlanUpdateRequest;
import com.example.cp.dto.plan.CpPlanPageRequest;
import com.example.cp.exception.CpBusinessException;
import com.example.cp.mapper.CpPathwayPlanMapper;
import com.example.cp.mapper.CpComplianceRateMapper;
import com.example.cp.model.CpPathwayPlan;
import com.example.cp.queue.RedisQueueService1;
import com.example.cp.service.monitor.CpDeviationService;

import com.mybatisflex.core.paginate.Page;
import com.mybatisflex.core.query.QueryWrapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * CpPlanCrudService 单元测试
 */
@ExtendWith(MockitoExtension.class)
class CpPlanCrudServiceTest {

    @Mock
    private CpPathwayPlanMapper cpPathwayPlanMapper;
    @Mock
    private CpComplianceRateMapper cpComplianceRateMapper;
    @Mock
    private CpPlanAssemblyService cpPlanAssemblyService;
    @Mock
    private CpPlanCacheService cpPlanCacheService;
    @Mock
    private CpPlanChangeService cpPlanChangeService;
    @Mock
    private CpDeviationService cpDeviationService;
    @Mock
    private RedisQueueService1 redisQueueService;

    private CpPlanCrudService cpPlanCrudService;

    @BeforeEach
    void setUp() {
        cpPlanCrudService = new CpPlanCrudService(
                cpPathwayPlanMapper, cpComplianceRateMapper,
                cpPlanAssemblyService, cpPlanCacheService,
                cpPlanChangeService, cpDeviationService,
                redisQueueService);
    }

    @Test
    void testGetPlanById_success() {
        CpPathwayPlan plan = new CpPathwayPlan();
        plan.setId("plan-1");
        plan.setLabCode("LAB001");
        plan.setIsDeleted(0);

        CpPlanDto dto = new CpPlanDto();
        dto.setId("plan-1");

        when(cpPlanCacheService.get("plan-1")).thenReturn(null);
        when(cpPathwayPlanMapper.selectOneById("plan-1")).thenReturn(plan);
        when(cpPlanAssemblyService.assemblePlanDto(plan)).thenReturn(dto);

        CpPlanDto result = cpPlanCrudService.getPlanById("plan-1");
        assertNotNull(result);
        assertEquals("plan-1", result.getId());
        verify(cpPlanCacheService).set(eq("plan-1"), eq(dto), anyLong());
    }

    @Test
    void testGetPlanById_notFound() {
        when(cpPlanCacheService.get("plan-999")).thenReturn(null);
        when(cpPathwayPlanMapper.selectOneById("plan-999")).thenReturn(null);

        assertThrows(CpBusinessException.class, () -> cpPlanCrudService.getPlanById("plan-999"));
    }

    @Test
    void testGetPlanById_fromCache() {
        CpPlanDto cached = new CpPlanDto();
        cached.setId("plan-1");
        when(cpPlanCacheService.get("plan-1")).thenReturn(cached);

        CpPlanDto result = cpPlanCrudService.getPlanById("plan-1");
        assertNotNull(result);
        assertEquals("plan-1", result.getId());
        verify(cpPathwayPlanMapper, never()).selectOneById(anyString());
    }

    @Test
    void testCountPlanByStatus_success() {
        when(cpPathwayPlanMapper.selectCountByQuery(any(QueryWrapper.class))).thenReturn(5L);

        Map<String, Long> result = cpPlanCrudService.countPlanByStatus("LAB001");
        assertEquals(3, result.size());
        assertTrue(result.containsKey("active"));
        assertTrue(result.containsKey("disabled"));
        assertTrue(result.containsKey("total"));
    }

    @Test
    void testQueryPlanPage_success() {
        CpPlanPageRequest request = new CpPlanPageRequest();
        request.setLabCode("LAB001");
        request.setPageNum(1);
        request.setPageSize(20);

        CpPathwayPlan plan = new CpPathwayPlan();
        plan.setId("plan-1");
        plan.setLabCode("LAB001");

        Page<CpPathwayPlan> planPage = new Page<>();
        planPage.setRecords(List.of(plan));
        planPage.setPageNumber(1);
        planPage.setPageSize(20);
        planPage.setTotalRow(1);

        when(cpPathwayPlanMapper.paginate(any(Page.class), any(QueryWrapper.class))).thenReturn(planPage);
        when(cpPlanAssemblyService.assemblePlanDto(plan)).thenReturn(new CpPlanDto());

        Page<CpPlanDto> result = cpPlanCrudService.queryPlanPage(request);
        assertNotNull(result);
        assertEquals(1, result.getRecords().size());
    }
}
