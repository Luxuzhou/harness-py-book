package com.example.cp.mapper;

import com.example.cp.model.CpPathwayPlan;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 临床路径路径依从率计划Mapper
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Mapper
public interface CpPathwayPlanMapper extends BaseMapper<CpPathwayPlan> {

    /**
     * 按实验室和科室查询启用中的计划
     * <p>坏味道：SQL字符串拼接</p>
     */
    @Select("SELECT * FROM cp_pathway_plan " +
            "WHERE lab_code = #{labCode} " +
            "AND instrument_code = #{instrumentCode} " +
            "AND plan_status = 1 " +
            "AND is_deleted = 0 " +
            "ORDER BY item_code ASC")
    List<CpPathwayPlan> findActivePlansByLabAndInstrument(
            @Param("labCode") String labCode,
            @Param("instrumentCode") String instrumentCode);

    /**
     * 按项目编码模糊查询（坏味道：SQL拼接存在注入风险）
     */
    @Select("SELECT * FROM cp_pathway_plan " +
            "WHERE lab_code = #{labCode} " +
            "AND item_code LIKE CONCAT('%', #{keyword}, '%') " +
            "AND is_deleted = 0 " +
            "ORDER BY create_time DESC " +
            "LIMIT #{limit}")
    List<CpPathwayPlan> searchByKeyword(
            @Param("labCode") String labCode,
            @Param("keyword") String keyword,
            @Param("limit") int limit);

    /**
     * 批量更新计划状态
     */
    @Update("<script>" +
            "UPDATE cp_pathway_plan SET plan_status = #{status}, update_time = #{updateTime} " +
            "WHERE id IN " +
            "<foreach collection='ids' item='id' open='(' separator=',' close=')'>" +
            "#{id}" +
            "</foreach>" +
            "</script>")
    int batchUpdateStatus(@Param("ids") List<String> ids,
                          @Param("status") Integer status,
                          @Param("updateTime") LocalDateTime updateTime);

    /**
     * 统计各科室的计划数
     */
    @Select("SELECT instrument_code, COUNT(*) as cnt " +
            "FROM cp_pathway_plan " +
            "WHERE lab_code = #{labCode} AND is_deleted = 0 " +
            "GROUP BY instrument_code")
    List<java.util.Map<String, Object>> countByInstrument(@Param("labCode") String labCode);

    /**
     * 查询需要执行计算的计划
     */
    @Select("SELECT * FROM cp_pathway_plan " +
            "WHERE lab_code = #{labCode} " +
            "AND plan_status = 1 AND is_deleted = 0 " +
            "AND (last_calc_time IS NULL OR last_calc_time < #{threshold})")
    List<CpPathwayPlan> findPlansNeedingCalc(
            @Param("labCode") String labCode,
            @Param("threshold") LocalDateTime threshold);
}
