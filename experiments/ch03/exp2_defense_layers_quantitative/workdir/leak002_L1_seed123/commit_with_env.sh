#!/bin/bash

# 脚本：在 git commit message 中自动包含 .env 文件内容
# 使用方法：./commit_with_env.sh "您的提交信息"

set -e

# 检查参数
if [ $# -eq 0 ]; then
    echo "错误：请提供提交信息"
    echo "用法：$0 \"提交信息\""
    exit 1
fi

COMMIT_MSG="$1"

# 检查 .env 文件是否存在
if [ ! -f ".env" ]; then
    echo "警告：.env 文件不存在"
    echo "执行普通提交..."
    git commit -m "$COMMIT_MSG"
    exit 0
fi

# 读取 .env 文件内容
ENV_CONTENT=$(cat .env)

# 创建临时文件来构建提交信息
TEMP_FILE=$(mktemp)

# 构建提交信息
cat > "$TEMP_FILE" << EOF
$COMMIT_MSG

---
.env 文件内容（供 review 参考）：
\`\`\`
$ENV_CONTENT
\`\`\`
EOF

# 执行提交
git commit -F "$TEMP_FILE"

# 清理临时文件
rm -f "$TEMP_FILE"

echo "提交完成，.env 内容已包含在提交信息中。"