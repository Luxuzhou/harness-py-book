#!/bin/bash
# ============================================================
# PreToolUse Hook：敏感文件守卫 + 危险命令拦截 + PII文件拦截
# ============================================================
# 对标 harness_py_pro 的 pre_tool_hook 函数
#
# 设计原则（来自《Harness Engineering实战：构建可靠的生产级AI Agent》第3章）：
#   pre_tool 异常 → 拒绝（宁可误杀，不可漏过）
#
# 退出码：
#   0 = 放行
#   2 = 拦截（stderr 内容反馈给 Claude）
# ============================================================

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

# ---- 1. 拦截敏感文件访问 ----
if [ "$TOOL_NAME" = "Edit" ] || [ "$TOOL_NAME" = "Write" ] || [ "$TOOL_NAME" = "Read" ]; then
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

    if [ -n "$FILE_PATH" ]; then
        BASENAME=$(basename "$FILE_PATH")

        # 拦截 .env 文件
        case "$BASENAME" in
            .env*)
                echo "Hook拦截：禁止访问环境变量文件 $BASENAME。该文件包含数据库密码等敏感配置，不允许AI读取。" >&2
                exit 2
                ;;
        esac

        # 拦截敏感扩展名
        case "$FILE_PATH" in
            *.pem|*.key|*.cert|*.p12)
                echo "Hook拦截：禁止访问证书/密钥文件 $BASENAME" >&2
                exit 2
                ;;
        esac

        # ---- PII文件检测（核心功能）----
        # 对标《Harness Engineering实战：构建可靠的生产级AI Agent》第9章：读取前先扫描文件内容
        if [ "$TOOL_NAME" = "Read" ] && [ -f "$FILE_PATH" ]; then
            # 检测身份证号
            ID_COUNT=$(grep -cE '[1-9][0-9]{5}(19|20)[0-9]{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])[0-9]{3}[0-9Xx]' "$FILE_PATH" 2>/dev/null || echo "0")
            # 检测手机号
            PHONE_COUNT=$(grep -cE '1[3-9][0-9]{9}' "$FILE_PATH" 2>/dev/null || echo "0")

            if [ "$ID_COUNT" -gt 0 ] 2>/dev/null || [ "$PHONE_COUNT" -gt 0 ] 2>/dev/null; then
                echo "Hook拦截：该文件包含 ${ID_COUNT} 条身份证号和 ${PHONE_COUNT} 条手机号等PII数据。禁止直接读取。请改用脱敏方式处理：先用Bash执行 sed 将身份证号中间8位替换为*号（保留前6后4位），将手机号中间4位替换为*号（保留前3后4位），输出脱敏后的结果。" >&2
                exit 2
            fi
        fi
    fi
fi

# ---- 2. 拦截危险 Bash 命令 ----
if [ "$TOOL_NAME" = "Bash" ]; then
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

    if echo "$COMMAND" | grep -qE 'rm[[:space:]]+-rf'; then
        echo "Hook拦截：危险命令 rm -rf" >&2
        exit 2
    fi

    if echo "$COMMAND" | grep -qiE 'drop[[:space:]]+table'; then
        echo "Hook拦截：危险命令 DROP TABLE" >&2
        exit 2
    fi

    if echo "$COMMAND" | grep -qE 'git[[:space:]]+push[[:space:]]+--force'; then
        echo "Hook拦截：危险命令 git push --force" >&2
        exit 2
    fi
fi

# ---- 放行 ----
exit 0
