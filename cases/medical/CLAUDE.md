# Medical Data Analysis — Harness Configuration

## 项目信息
三甲医院检验科血常规数据分析项目。数据已脱敏但仍需遵守医疗数据处理规范。

## 合规约束（最高优先级）

### 数据隔离
- 只允许读取 `sample_data/` 目录下的文件
- 只允许写入当前案例目录（`cases/medical/`）
- 禁止访问系统目录、用户目录、网络资源

### 输出过滤
- 所有输出中禁止包含 `PAT-\d{5}` 格式的患者ID
- 如果分析需要引用具体病例，使用序号替代（如"第37例"）
- 禁止输出单条记录的完整字段

### 网络隔离
- 禁止使用 bash 执行任何网络命令（curl, wget, ping, ssh, nc）
- 禁止使用 Python 的 requests, urllib, socket 模块

### 审计要求
- 每次文件读取操作记录到 `compliance_log.jsonl`
- 记录格式：`{"time": "ISO8601", "action": "read", "file": "path", "tool": "tool_name"}`

## 工具使用规则
- `read_file`：仅限 `sample_data/` 目录
- `write_file`：仅限当前案例目录，且输出内容经过合规检查
- `bash`：仅限运行 Python 数据分析脚本，禁止网络命令
- `edit_file`：允许，用于修改分析脚本
- `grep_search` / `glob_search`：仅限 `sample_data/` 和当前目录

## 分析规范
- 使用标准库（csv, json, statistics）即可，不要求安装第三方包
- 统计结果保留2位小数
- 年龄分组：0-17, 18-44, 45-64, 65+
