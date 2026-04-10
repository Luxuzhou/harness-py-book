package com.example.sqc.alarm.service;

import org.springframework.stereotype.Service;

/**
 * 智能报警业务逻辑服务。
 *
 * <p>骨架代码 — Agent 需要补充：
 * <ul>
 *   <li>createRule(dto) — 创建报警规则，检查重复</li>
 *   <li>getRuleByTestItemId(testItemId) — 按检验项目ID查询规则</li>
 *   <li>createEvent(dto) — 记录报警事件</li>
 * </ul>
 *
 * <p>实现要求：
 * <ul>
 *   <li>写操作添加 @Transactional</li>
 *   <li>读操作添加 @Transactional(readOnly = true)</li>
 *   <li>Entity 与 DTO 之间的转换在本层完成</li>
 *   <li>规则已存在时抛出自定义异常（409）</li>
 *   <li>规则不存在时抛出自定义异常（404）</li>
 * </ul>
 */
@Service
public class AlarmService {

    // TODO: 注入 AlarmRuleRepository 和 AlarmEventRepository

    // TODO: createRule(AlarmRuleDto dto) -> AlarmRuleDto

    // TODO: getRuleByTestItemId(String testItemId) -> AlarmRuleDto

    // TODO: createEvent(AlarmEventDto dto) -> AlarmEventDto
}
