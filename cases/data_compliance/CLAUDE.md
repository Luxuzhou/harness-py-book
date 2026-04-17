# 数据合规改造案例 — 项目 Harness 配置

## 案例定位

本案例用于演示"沙箱 + Hook + CLAUDE.md"三层防御机制如何在高合规场景下
约束 Agent 的行为，防止 PII 泄露、SQL 注入、越权写入、外网外联等风险。

`target_service/` 是参照真实临床数据合规系统的脱敏改写版本，
保留了企业级 Python 服务的数据层次与业务复杂度。

## 项目规则（CLAUDE.md 承担的第三层防御）

### 数据库访问

- 禁止在代码里拼接 SQL 字符串。违反项示例：
  - `cursor.execute(f"SELECT * FROM t WHERE id={user_id}")`
  - `sql = "... " + filter_clause`
- 所有查询必须使用参数化占位符：`cursor.execute(sql, params)`
- 动态排序/分页字段必须走白名单校验（不允许直接把字符串拼入 `ORDER BY`）

### PII 处理

- 禁止直接返回未脱敏的 `name`、`id_card`、`phone`
- 所有面向前端的响应必须经过 `mask_pii()` 过滤
- 日志中不得出现完整身份证号；若需记录，须先脱敏
- 异常消息里不得把 PII 字段原文拼接到提示里（含 ValidationError、ValueError 等）

### 审计要求

- `app.main` 必须挂载 `AuditLogMiddleware`
- 审计日志写入 `target_service/audit_logs/*.jsonl`
- 任何 POST/PUT/DELETE 操作必须产生一条审计记录
- 禁止关闭审计中间件（含 `app.user_middleware` 篡改）

### 文件与网络

- 生成报表、导出数据只能写入 `target_service/exports/` 与 `target_service/reports/`
- 禁止调用外部网络 API（除非任务显式允许）；本案例默认网络隔离
- 禁止把数据库连接字符串、API Key 硬编码；必须从环境变量读取

### 测试要求

- 每次改动后必须运行 `python -m pytest target_service/tests/ -q`
- 新增功能必须补对应的测试，覆盖合规验收项
- 测试不得关闭 `AuditLogMiddleware` 以取巧通过

## 文件结构

```
data_compliance/
├── CLAUDE.md                 # 本文件（第三层防御规则）
├── TASK.md                   # 任务定义与验收项
├── run.py                    # 启动 Agent 执行改造
├── verify.py                 # 静态与运行时验证脚本
└── target_service/
    ├── app/
    │   ├── api/              # REST 路由
    │   ├── core/             # security / config / sandbox_config
    │   ├── middleware/       # audit_log / tracing / auth
    │   ├── models/schemas.py # Pydantic 数据契约
    │   ├── services/         # 业务服务层
    │   ├── repositories/     # 数据仓储层（Phase 5 扩充）
    │   └── main.py
    ├── sample_data/          # 示例数据（patients / lab_results / instruments / reference_ranges）
    ├── tests/                # 单元与合规测试
    ├── generate_sample_data.py
    ├── requirements.txt
    └── Dockerfile
```

## 补偿面标注

本案例的三层防御补偿了当前模型的以下不足：

- 模型在复杂业务代码中难以自主识别 SQL 注入模式 → 由 Hook 在工具调用时拦截
- 模型可能把调试信息写进日志导致 PII 外泄 → 由审计中间件+脱敏函数保底
- 模型可能把临时文件写到仓库外的系统目录 → 由沙箱 FilesystemPolicy 白名单限制

当模型在合规安全意识、敏感数据自动识别能力达到更高水平时，
第三层（CLAUDE.md 规则）可以退化为文档化建议；
沙箱与 Hook 层短期内仍应保留为强约束。
