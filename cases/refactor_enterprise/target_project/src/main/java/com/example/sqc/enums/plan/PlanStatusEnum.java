package com.example.sqc.enums.plan;

import lombok.Getter;

/**
 * 质控计划状态枚举
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Getter
public enum PlanStatusEnum {

    DISABLED(0, "禁用"),
    ENABLED(1, "启用"),
    DRAFT(2, "草稿"),
    ARCHIVED(3, "归档");

    private final int code;
    private final String name;

    PlanStatusEnum(int code, String name) {
        this.code = code;
        this.name = name;
    }

    public static PlanStatusEnum fromCode(int code) {
        for (PlanStatusEnum e : values()) {
            if (e.getCode() == code) {
                return e;
            }
        }
        return null;
    }
}
