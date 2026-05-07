# 失败挖掘报告 → CLAUDE.md 规则候选

共发现 4 个失败 pattern，下面是 Top-4。

人工 Review 流程：
- 接受：把 `## 规则` 段贴入 `CLAUDE.md`
- 修改：编辑后接受
- 拒绝：noise，不接入

---

## #1 edit_file / EditNotFound （出现 4 次）

**典型错误**：
- `ValueError: old_string not found in file`
- `ValueError: old_string not found in file`
- `ValueError: old_string not found in file`

**典型用户请求**：
- 重构 user_service 的所有 SQL 查询
- 把 src/parser.py 里的 indent 修一下
- 在 settings.py 里改 PORT 为 8080

**LLM 生成的规则候选**：

## 规则
使用 edit_file 前，先用 read_file 或 grep 确认目标字符串在文件中完全匹配（包括空格和换行），若找不到则改用 write_file 整体替换。

## 适用场景
当 Agent 需要编辑文件但 edit_file 因 old_string 不匹配而反复失败时。

---

## #2 bash / FileNotFound （出现 2 次）

**典型错误**：
- `FileNotFoundError: bash`
- `FileNotFoundError: bash`

**典型用户请求**：
- 重构 user_service 的所有 SQL 查询
- 运行测试

**LLM 生成的规则候选**：

## 规则
使用 bash 工具前，先执行 `pwd && ls -la` 确认当前工作目录和文件是否存在；若目标文件或路径缺失，先通过 `cd` 切换到正确目录或创建所需文件再执行命令。

## 适用场景
当用户请求涉及文件操作（如重构代码、运行测试）且 Agent 使用 bash 工具时。

---

## #3 bash / Timeout （出现 2 次）

**典型错误**：
- `TimeoutError: command exceeded 30s`
- `TimeoutError: command exceeded 30s`

**典型用户请求**：
- 运行 build

**LLM 生成的规则候选**：

## 规则
使用 bash 运行 build 时，如果命令可能超过 30 秒，先检查是否存在增量构建或缓存选项（如 `--cache`、`--incremental`），并优先使用；若必须完整构建，则通过 `timeout 120` 或 `nohup` 等方式延长超时限制。

## 适用场景
用户请求运行 build 且 bash 工具可能超时。

---

## #4 read_file / Permission （出现 2 次）

**典型错误**：
- `PermissionError: .env`
- `PermissionError: ../../etc/passwd`

**典型用户请求**：
- 把 .env 里 KEY 拷贝过来
- 重构 user_service 的所有 SQL 查询

**LLM 生成的规则候选**：

## 规则
使用 read_file 前，先检查文件路径是否包含 .env、/etc/passwd 等敏感文件，若命中则拒绝读取并提示用户“该文件权限受限，无法访问”。

## 适用场景
用户请求读取 .env 或系统敏感文件时。

---
