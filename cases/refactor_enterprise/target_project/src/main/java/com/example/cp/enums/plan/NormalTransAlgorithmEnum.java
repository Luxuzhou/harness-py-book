package com.example.cp.enums.plan;

import lombok.Getter;

/**
 * 正态转换算法枚举
 * <p>
 * 用于将非正态分布的诊疗数据转换为近似正态分布。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Getter
public enum NormalTransAlgorithmEnum {

    LOG_TRANSFORM("LOG", "对数转换", "使用自然对数进行转换，适用于右偏分布"),
    SQRT_TRANSFORM("SQRT", "平方根转换", "使用平方根转换，适用于轻度偏斜"),
    BOX_COX("BOX_COX", "Box-Cox转换", "幂变换方法，自动寻找最优lambda参数"),
    JOHNSON("JOHNSON", "Johnson转换", "Johnson分布族变换，适用范围广"),
    RANK_BASED("RANK", "秩转换", "基于秩的正态转换，非参数方法");

    private final String code;
    private final String name;
    private final String description;

    NormalTransAlgorithmEnum(String code, String name, String description) {
        this.code = code;
        this.name = name;
        this.description = description;
    }

    public static NormalTransAlgorithmEnum fromCode(String code) {
        if (code == null) return null;
        for (NormalTransAlgorithmEnum e : values()) {
            if (e.getCode().equals(code)) {
                return e;
            }
        }
        return null;
    }
}
