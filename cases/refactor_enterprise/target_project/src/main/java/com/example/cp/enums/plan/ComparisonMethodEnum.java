package com.example.cp.enums.plan;

import lombok.Getter;

/**
 * 比对方法枚举
 *
 * @author cp-team
 * @since 2024-02-25
 */
@Getter
public enum ComparisonMethodEnum {

    PASSING_BABLOK("PASSING_BABLOK", "Passing-Bablok回归", "非参数回归方法，对离群值不敏感"),
    DEMING("DEMING", "Deming回归", "考虑双方误差的回归方法"),
    BLAND_ALTMAN("BLAND_ALTMAN", "Bland-Altman分析", "差值分析法，评估一致性"),
    LINEAR_REGRESSION("LINEAR_REGRESSION", "线性回归", "最小二乘法线性回归");

    private final String code;
    private final String name;
    private final String description;

    ComparisonMethodEnum(String code, String name, String description) {
        this.code = code;
        this.name = name;
        this.description = description;
    }

    public static ComparisonMethodEnum fromCode(String code) {
        if (code == null) return null;
        for (ComparisonMethodEnum e : values()) {
            if (e.getCode().equals(code)) {
                return e;
            }
        }
        return null;
    }
}
