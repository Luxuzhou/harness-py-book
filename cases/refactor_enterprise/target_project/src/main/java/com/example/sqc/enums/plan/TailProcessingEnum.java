package com.example.sqc.enums.plan;

import lombok.Getter;

/**
 * 尾数处理方式枚举
 * <p>
 * 定义检验结果数值的小数位保留规则。
 * </p>
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Getter
public enum TailProcessingEnum {

    ROUND_0("ROUND_0", "取整", 0),
    ROUND_1("ROUND_1", "保留1位小数", 1),
    ROUND_2("ROUND_2", "保留2位小数", 2),
    ROUND_3("ROUND_3", "保留3位小数", 3),
    ROUND_4("ROUND_4", "保留4位小数", 4),
    ROUND_6("ROUND_6", "保留6位小数", 6);

    private final String code;
    private final String name;
    private final int decimalPlaces;

    TailProcessingEnum(String code, String name, int decimalPlaces) {
        this.code = code;
        this.name = name;
        this.decimalPlaces = decimalPlaces;
    }

    public static TailProcessingEnum fromCode(String code) {
        if (code == null) return null;
        for (TailProcessingEnum e : values()) {
            if (e.getCode().equals(code)) {
                return e;
            }
        }
        return null;
    }
}
