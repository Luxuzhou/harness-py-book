package com.example.cp.mapper;

import com.example.cp.model.CpPathwayVariation;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 临床路径方案变更记录Mapper
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Mapper
public interface CpPathwayVariationMapper extends BaseMapper<CpPathwayVariation> {

    @Select("SELECT * FROM cp_pathway_change " +
            "WHERE plan_id = #{planId} " +
            "ORDER BY change_time DESC " +
            "LIMIT #{limit}")
    List<CpPathwayVariation> findRecentChanges(
            @Param("planId") String planId,
            @Param("limit") int limit);

    @Select("SELECT * FROM cp_pathway_change " +
            "WHERE plan_id = #{planId} " +
            "AND change_time BETWEEN #{startTime} AND #{endTime} " +
            "ORDER BY change_time DESC")
    List<CpPathwayVariation> findChangesByTimeRange(
            @Param("planId") String planId,
            @Param("startTime") LocalDateTime startTime,
            @Param("endTime") LocalDateTime endTime);

    @Select("SELECT field_name, COUNT(*) as change_count " +
            "FROM cp_pathway_change " +
            "WHERE plan_id = #{planId} " +
            "GROUP BY field_name " +
            "ORDER BY change_count DESC")
    List<java.util.Map<String, Object>> countChangesByField(@Param("planId") String planId);
}
