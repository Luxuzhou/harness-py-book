package com.example.sqc.enums.monitor;

import lombok.Getter;

/**
 * 报警级别枚举
 *
 * @author sqc-team
 * @since 2024-03-20
 */
@Getter
public enum AlarmLevelEnum {

    NORMAL("NORMAL", "正常", 0),
    WARNING("WARNING", "警告", 1),
    ERROR("ERROR", "异常", 2),
    CRITICAL("CRITICAL", "严重", 3);

    private final String code;
    private final String name;
    private final int priority;

    AlarmLevelEnum(String code, String name, int priority) {
        this.code = code;
        this.name = name;
        this.priority = priority;
    }

    public static AlarmLevelEnum fromCode(String code) {
        if (code == null) return null;
        for (AlarmLevelEnum e : values()) {
            if (e.getCode().equals(code)) {
                return e;
            }
        }
        return null;
    }
}
