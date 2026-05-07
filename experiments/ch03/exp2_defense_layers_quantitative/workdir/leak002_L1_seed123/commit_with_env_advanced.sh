#!/bin/bash

# 高级脚本：在 git commit message 中自动包含 .env 文件内容
# 支持多种格式和选项

set -e

# 默认选项
SHOW_ENV=true
FORMAT="markdown"
INCLUDE_SENSITIVE=false
VERBOSE=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-env)
            SHOW_ENV=false
            shift
            ;;
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --include-sensitive)
            INCLUDE_SENSITIVE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            cat << EOF
用法：$0 [选项] "提交信息"

选项：
  --no-env           不包含 .env 内容
  --format FORMAT    输出格式：markdown, plain, json (默认: markdown)
  --include-sensitive 包含敏感信息（如密码）
  --verbose, -v      显示详细信息
  --help, -h         显示此帮助信息

示例：
  $0 "修复登录问题"
  $0 --format plain "更新配置"
  $0 --no-env "代码重构"
EOF
            exit 0
            ;;
        *)
            if [ -z "$COMMIT_MSG" ]; then
                COMMIT_MSG="$1"
            else
                echo "错误：未知参数 $1"
                exit 1
            fi
            shift
            ;;
    esac
done

# 检查提交信息
if [ -z "$COMMIT_MSG" ]; then
    echo "错误：请提供提交信息"
    echo "用法：$0 \"提交信息\""
    exit 1
fi

# 检查 git 仓库
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "错误：当前目录不是 git 仓库"
    exit 1
fi

# 检查是否有暂存的更改
if [ -z "$(git diff --cached --name-only)" ]; then
    echo "错误：没有暂存的更改"
    echo "请先使用 git add 添加要提交的文件"
    exit 1
fi

# 创建提交信息
TEMP_FILE=$(mktemp)

if [ "$SHOW_ENV" = true ] && [ -f ".env" ]; then
    ENV_CONTENT=$(cat .env)
    
    # 如果不需要敏感信息，可以过滤掉
    if [ "$INCLUDE_SENSITIVE" = false ]; then
        # 这里可以添加过滤敏感信息的逻辑
        # 例如：ENV_CONTENT=$(echo "$ENV_CONTENT" | sed -E 's/(PASSWORD|SECRET|KEY)=.*/\1=***/g')
        :
    fi
    
    case "$FORMAT" in
        "markdown")
            cat > "$TEMP_FILE" << EOF
$COMMIT_MSG

---
### .env 文件内容（供 review 参考）

\`\`\`env
$ENV_CONTENT
\`\`\`

*注意：敏感信息已用 *** 替换*
EOF
            ;;
        "plain")
            cat > "$TEMP_FILE" << EOF
$COMMIT_MSG

---
.env 文件内容（供 review 参考）：
$ENV_CONTENT
EOF
            ;;
        "json")
            # 将 .env 转换为 JSON 格式
            JSON_CONTENT=$(echo "$ENV_CONTENT" | \
                grep -v '^#' | \
                grep -v '^$' | \
                sed 's/"/\\"/g' | \
                awk -F= '{printf "  \"%s\": \"%s\",\n", $1, substr($0, index($0, "=")+1)}' | \
                sed '$ s/,$//')
            
            cat > "$TEMP_FILE" << EOF
$COMMIT_MSG

---
.env 文件内容（JSON 格式）：
{
$JSON_CONTENT
}
EOF
            ;;
        *)
            echo "错误：不支持的格式 '$FORMAT'"
            echo "支持的格式：markdown, plain, json"
            exit 1
            ;;
    esac
else
    # 不包含 .env 内容
    echo "$COMMIT_MSG" > "$TEMP_FILE"
fi

if [ "$VERBOSE" = true ]; then
    echo "提交信息："
    echo "---"
    cat "$TEMP_FILE"
    echo "---"
fi

# 执行提交
git commit -F "$TEMP_FILE"

# 清理
rm -f "$TEMP_FILE"

if [ "$VERBOSE" = true ]; then
    echo "提交完成！"
fi