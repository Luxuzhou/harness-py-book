package com.example.cp.service.plan;

import com.example.cp.dto.plan.CpPlanApplyRequest;
import com.example.cp.mapper.CpPathwayPlanMapper;
import com.example.cp.mapper.CpComplianceRateMapper;
import com.example.cp.mapper.ck.BiTreatmentRecordMapper;
import com.example.cp.model.CpPathwayPlan;
import com.example.cp.model.ck.BiTreatmentRecord;
import com.example.cp.service.monitor.CpDeviationService;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * CpPlanCalculationService 单元测试
 */
@ExtendWith(MockitoExtension.class)
class CpPlanCalculationServiceTest {

    @Mock
    private CpPathwayPlanMapper cpPathwayPlanMapper;
    @Mock
    private CpComplianceRateMapper cpComplianceRateMapper;
    @Mock
    private BiTreatmentRecordMapper biInspectResultMapper;
    @Mock
    private CpDeviationService cpDeviationService;

    private CpPlanCalculationService cpPlanCalculationService;

    @BeforeEach
    void setUp() {
        cpPlanCalculationService = new CpPlanCalculationService(
                cpPathwayPlanMapper, cpComplianceRateMapper,
                biInspectResultMapper, cpDeviationService);
    }

    @Test
    void testApplyCpPathwayPlan_noData() {
        CpPlanApplyRequest request = CpPlanApplyRequest.builder()
                .planId("plan-1")
                .labCode("LAB001")
                .instrumentCode("INS001")
                .itemCode("ITEM001")
                .algorithmCode("WESTGARD")
                .movingWindow(20)
                .startDate(LocalDate.now().minusDays(30))
                .endDate(LocalDate.now())
                .build();

        when(biInspectResultMapper.queryByCondition(anyString(), anyString(), anyString(), any(),
                any(LocalDateTime.class), any(LocalDateTime.class)))
                .thenReturn(Collections.emptyList());

        Map<String, Object> result = cpPlanCalculationService.applyCpPathwayPlan(request);
        assertNotNull(result);
        assertFalse((Boolean) result.get("success"));
        assertEquals("未查询到诊疗数据", result.get("message"));
    }

    @Test
    void testApplyCpPathwayPlan_success() {
        BiTreatmentRecord record = new BiTreatmentRecord();
        record.setResultValue(new BigDecimal("100"));
        record.setInspectTime(LocalDateTime.now());

        CpPlanApplyRequest request = CpPlanApplyRequest.builder()
                .planId("plan-1")
                .labCode("LAB001")
                .instrumentCode("INS001")
                .itemCode("ITEM001")
                .algorithmCode("WESTGARD")
                .movingWindow(5)
                .startDate(LocalDate.now().minusDays(30))
                .endDate(LocalDate.now())
                .build();

        when(biInspectResultMapper.queryByCondition(anyString(), anyString(), anyString(), any(),
                any(LocalDateTime.class), any(LocalDateTime.class)))
                .thenReturn(List.of(record, record, record, record, record, record));

        CpPathwayPlan plan = new CpPathwayPlan();
        plan.setId("plan-1");
        when(cpPathwayPlanMapper.selectOneById("plan-1")).thenReturn(plan);

        Map<String, Object> result = cpPlanCalculationService.applyCpPathwayPlan(request);
        assertNotNull(result);
        assertTrue((Boolean) result.get("success"));
        verify(cpPathwayPlanMapper).update(any(CpPathwayPlan.class));
    }

    @Test
    void testApplyCpPathwayPlan_with15Params() {
        when(biInspectResultMapper.queryByCondition(anyString(), anyString(), anyString(), any(),
                any(LocalDateTime.class), any(LocalDateTime.class)))
                .thenReturn(Collections.emptyList());

        Map<String, Object> result = cpPlanCalculationService.applyCpPathwayPlan(
                "plan-1", "LAB001", "INS001", "ITEM001",
                null, null, "WESTGARD", 20,
                null, null, null, null, false,
                LocalDate.now().minusDays(30), LocalDate.now());

        assertNotNull(result);
        assertFalse((Boolean) result.get("success"));
    }

    @Test
    void testApplyCpPathwayPlan_invalidPlanId() {
        CpPlanApplyRequest request = CpPlanApplyRequest.builder()
                .planId("")
                .labCode("LAB001")
                .instrumentCode("INS001")
                .itemCode("ITEM001")
                .algorithmCode("WESTGARD")
                .build();

        assertThrows(com.example.cp.exception.CpBusinessException.class,
                () -> cpPlanCalculationService.applyCpPathwayPlan(request));
    }
}
