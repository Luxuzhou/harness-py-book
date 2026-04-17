package com.example.cp.enums.monitor;

import lombok.Getter;

/**
 * 偏差监测任务状态枚举
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Getter
public enum MonitorStatusEnum {

    PENDING("PENDING", "待执行"),
    RUNNING("RUNNING", "执行中"),
    COMPLETED("COMPLETED", "已完成"),
    FAILED("FAILED", "失败"),
    CANCELLED("CANCELLED", "已取消"),
    TIMEOUT("TIMEOUT", "超时");

    private final String code;
    private final String name;

    MonitorStatusEnum(String code, String name) {
        this.code = code;
        this.name = name;
    }

    public static MonitorStatusEnum fromCode(String code) {
        if (code == null) return null;
        for (MonitorStatusEnum e : values()) {
            if (e.getCode().equals(code)) {
                return e;
            }
        }
        return null;
    }
}
