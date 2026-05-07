package com.example.cp.mapper;

import com.example.cp.model.AnomalyRule;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * 智能预警规则 Mapper
 * <p>
 * 提供对 anomaly_rule 表的基础 CRUD 操作及自定义查询。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Mapper
public interface AnomalyRuleMapper extends BaseMapper<AnomalyRule> {

    /**
     * 按诊疗项目ID查询预警规则
     *
     * @param testItemId 诊疗项目ID
     * @return 预警规则实体，不存在时返回 null
     */
    @Select("SELECT * FROM anomaly_rule WHERE test_item_id = #{testItemId}")
    AnomalyRule findByTestItemId(@Param("testItemId") String testItemId);

    /**
     * 检查诊疗项目是否已存在预警规则
     *
     * @param testItemId 诊疗项目ID
     * @return 存在返回 true，否则返回 false
     */
    @Select("SELECT COUNT(1) FROM anomaly_rule WHERE test_item_id = #{testItemId}")
    boolean existsByTestItemId(@Param("testItemId") String testItemId);
}
