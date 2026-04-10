package com.example.sqc.alarm.controller;

import com.example.sqc.alarm.dto.AlarmRuleDto;
import com.example.sqc.alarm.service.AlarmService;
import org.springframework.web.bind.annotation.*;

/**
 * 智能报警 REST API 控制器。
 *
 * <p>骨架代码 — Agent 需要补充：
 * <ul>
 *   <li>POST /api/v1/alarm/rules — 创建报警规则</li>
 *   <li>GET  /api/v1/alarm/rules/{testItemId} — 查询报警规则</li>
 *   <li>POST /api/v1/alarm/events — 记录报警事件（由 Python 端调用）</li>
 * </ul>
 *
 * <p>实现要求：
 * <ul>
 *   <li>参数校验使用 @Valid</li>
 *   <li>Service Token 校验从 X-Service-Token header 读取</li>
 *   <li>返回正确的 HTTP 状态码（201/200/400/401/404/409）</li>
 *   <li>JSON 字段使用 snake_case（通过 Jackson 全局配置）</li>
 * </ul>
 */
@RestController
@RequestMapping("/api/v1/alarm")
public class AlarmController {

    private final AlarmService alarmService;

    public AlarmController(AlarmService alarmService) {
        this.alarmService = alarmService;
    }

    // TODO: POST /rules — 创建报警规则
    // - 接收 @Valid @RequestBody AlarmRuleDto
    // - 返回 ResponseEntity<AlarmRuleDto> with status 201

    // TODO: GET /rules/{testItemId} — 查询报警规则
    // - 接收 @PathVariable String testItemId
    // - 返回 AlarmRuleDto or 404

    // TODO: POST /events — 记录报警事件
    // - 接收 @RequestHeader("X-Service-Token") String token
    // - 接收 @Valid @RequestBody AlarmEventDto
    // - 验证 token
    // - 返回 ResponseEntity with status 201
}
