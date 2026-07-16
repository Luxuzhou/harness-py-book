package com.example.cp.mapper;

import com.example.cp.model.CpClinicalVisit;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 临床路径诊疗样本Mapper
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Mapper
public interface CpClinicalVisitMapper extends BaseMapper<CpClinicalVisit> {

    @Select("SELECT * FROM cp_visit_sample " +
            "WHERE plan_id = #{planId} " +
            "AND inspect_time BETWEEN #{startTime} AND #{endTime} " +
            "AND is_deleted = 0 " +
            "ORDER BY inspect_time DESC")
    List<CpClinicalVisit> findByPlanAndTimeRange(
            @Param("planId") String planId,
            @Param("startTime") LocalDateTime startTime,
            @Param("endTime") LocalDateTime endTime);

    @Select("SELECT COUNT(*) FROM cp_visit_sample " +
            "WHERE plan_id = #{planId} AND is_deleted = 0")
    long countByPlan(@Param("planId") String planId);

    @Select("SELECT * FROM cp_visit_sample " +
            "WHERE plan_id = #{planId} AND is_deleted = 0 " +
            "ORDER BY inspect_time DESC LIMIT #{limit}")
    List<CpClinicalVisit> findRecentSamples(
            @Param("planId") String planId,
            @Param("limit") int limit);
}
