package com.example.cp.service.plan;

import com.example.cp.mapper.CpPathwayVariationMapper;
import com.example.cp.model.CpPathwayPlan;
import com.example.cp.model.CpPathwayVariation;

import com.mybatisflex.core.query.QueryWrapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * CpPlanChangeService 单元测试
 */
@ExtendWith(MockitoExtension.class)
class CpPlanChangeServiceTest {

    @Mock
    private CpPathwayVariationMapper cpPathwayVariationMapper;

    private CpPlanChangeService cpPlanChangeService;

    @BeforeEach
    void setUp() {
        cpPlanChangeService = new CpPlanChangeService(cpPathwayVariationMapper);
    }

    @Test
    void testRecordPlanChange_detectsChanges() {
        CpPathwayPlan before = new CpPathwayPlan();
        before.setAlgorithmCode("WESTGARD");
        before.setMovingWindow(20);

        CpPathwayPlan after = new CpPathwayPlan();
        after.setId("plan-1");
        after.setAlgorithmCode("MULTI_RULE");
        after.setMovingWindow(30);

        cpPlanChangeService.recordPlanChange(before, after, "admin");

        verify(cpPathwayVariationMapper, times(2)).insert(any(CpPathwayVariation.class));
    }

    @Test
    void testRecordPlanChange_noChanges() {
        CpPathwayPlan before = new CpPathwayPlan();
        before.setAlgorithmCode("WESTGARD");
        before.setMovingWindow(20);

        CpPathwayPlan after = new CpPathwayPlan();
        after.setId("plan-1");
        after.setAlgorithmCode("WESTGARD");
        after.setMovingWindow(20);

        cpPlanChangeService.recordPlanChange(before, after, "admin");

        verify(cpPathwayVariationMapper, never()).insert(any());
    }

    @Test
    void testQueryPlanChanges_success() {
        when(cpPathwayVariationMapper.selectListByQuery(any(QueryWrapper.class)))
                .thenReturn(Collections.singletonList(new CpPathwayVariation()));

        List<CpPathwayVariation> changes = cpPlanChangeService.queryPlanChanges(
                "plan-1", LocalDate.now().minusDays(7), LocalDate.now());

        assertEquals(1, changes.size());
    }

    @Test
    void testQueryPlanChanges_noDateRange() {
        when(cpPathwayVariationMapper.selectListByQuery(any(QueryWrapper.class)))
                .thenReturn(Collections.emptyList());

        List<CpPathwayVariation> changes = cpPlanChangeService.queryPlanChanges("plan-1", null, null);

        assertTrue(changes.isEmpty());
    }
}
