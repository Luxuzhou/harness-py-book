package com.example.cp.service.plan;

import com.example.cp.dto.plan.CpPlanDto;
import com.example.cp.mapper.CpComplianceRateMapper;
import com.example.cp.mapper.CpClinicalVisitMapper;
import com.example.cp.model.CpPathwayPlan;
import com.example.cp.model.CpComplianceRate;
import com.example.cp.service.monitor.CpDeviationService;

import com.mybatisflex.core.query.QueryWrapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * CpPlanAssemblyService 单元测试
 */
@ExtendWith(MockitoExtension.class)
class CpPlanAssemblyServiceTest {

    @Mock
    private CpComplianceRateMapper cpComplianceRateMapper;
    @Mock
    private CpClinicalVisitMapper cpClinicalVisitMapper;
    @Mock
    private CpDeviationService cpDeviationService;

    private CpPlanAssemblyService cpPlanAssemblyService;

    @BeforeEach
    void setUp() {
        cpPlanAssemblyService = new CpPlanAssemblyService(
                cpComplianceRateMapper, cpClinicalVisitMapper, cpDeviationService);
    }

    @Test
    void testAssemblePlanDto_success() {
        CpPathwayPlan plan = new CpPathwayPlan();
        plan.setId("plan-1");
        plan.setAlgorithmCode("WESTGARD");
        plan.setItemCode("ITEM001");

        CpComplianceRate latestAvg = new CpComplianceRate();
        latestAvg.setAvgMean(new java.math.BigDecimal("100"));

        when(cpComplianceRateMapper.selectOneByQuery(any(QueryWrapper.class))).thenReturn(latestAvg);
        when(cpClinicalVisitMapper.selectCountByQuery(any(QueryWrapper.class))).thenReturn(10L);
        when(cpDeviationService.countRecentAlarms("plan-1", 7)).thenReturn(2);

        CpPlanDto dto = cpPlanAssemblyService.assemblePlanDto(plan);
        assertNotNull(dto);
        assertEquals("plan-1", dto.getId());
        assertEquals(Integer.valueOf(10), dto.getSampleCount());
        assertEquals(Integer.valueOf(2), dto.getRecentAlarmCount());
    }

    @Test
    void testAssemblePlanDto_nullInput() {
        assertNull(cpPlanAssemblyService.assemblePlanDto(null));
    }

    @Test
    void testAssemblePlanDto_noComplianceData() {
        CpPathwayPlan plan = new CpPathwayPlan();
        plan.setId("plan-1");
        plan.setAlgorithmCode("WESTGARD");

        when(cpComplianceRateMapper.selectOneByQuery(any(QueryWrapper.class))).thenReturn(null);
        when(cpClinicalVisitMapper.selectCountByQuery(any(QueryWrapper.class))).thenReturn(0L);
        when(cpDeviationService.countRecentAlarms("plan-1", 7)).thenReturn(0);

        CpPlanDto dto = cpPlanAssemblyService.assemblePlanDto(plan);
        assertNotNull(dto);
        assertNull(dto.getLatestMean());
    }
}
