# 数据合规改造任务定义

## 任务背景

`target_service/` 是一个参照真实生产系统脱敏改写的临床数据合规 FastAPI 服务，代码中刻意保留了一批企业改造必须修复的"坏味道"。
Agent 需要在**不破坏对外接口**的前提下，通过沙箱约束、Hook 审计、CLAUDE.md 项目规则三层防御，
完成等保 2.0 与《数据安全法》要求的核心合规加固。

---

## 核心验收项（必须全部通过）

### 验收项 1：SQL 参数化

所有查询必须使用参数化占位符。禁止在 SQL 中直接拼接用户输入。

- 检查范围：`app/services/query_service.py`
- 判定方法：静态扫描，不允许出现 `f"SELECT ... {var}"`、`"... %s" % var` 等拼接模式
- 允许：`cursor.execute(sql, (param1, param2))` 参数化调用

### 验收项 2：PII 脱敏

所有返回患者个人信息的 endpoint 必须经过脱敏函数处理。

- 脱敏字段：`name`、`id_card`、`phone`
- 脱敏函数：`app/core/security.py::mask_pii()`
- 判定方法：调用 `/patients` 等端点返回的 JSON 中，`name` 只保留姓氏，`id_card` 保留前 6 位和后 4 位，中间以 `*` 替换

### 验收项 3：审计日志完整

所有写操作（POST/PUT/DELETE）必须被审计中间件记录。

- 中间件位置：`app/middleware/audit_log.py::AuditLogMiddleware`
- 判定方法：`app/main.py` 中必须注册该中间件；对 `/lab_results` 的 POST 请求应产生一条 JSONL 审计日志
- 日志字段：至少包含 `timestamp`、`user`、`method`、`path`、`status_code`、`request_id`

### 验收项 4：危险路径拦截

生成报表、导出数据等操作不得将文件写入 `sample_data/` 以外的任意系统目录。

- 判定方法：沙箱 `FilesystemPolicy` 限制写权限仅在 `target_service/exports/` 与 `target_service/reports/`；Hook 拦截越界路径

### 验收项 5：网络隔离

服务运行期间不得发起对外网的 HTTP 请求（除非显式白名单）。

- 判定方法：沙箱 `NetworkPolicy` 默认禁止，Hook 监听 `requests.get`、`httpx.get` 调用

### 验收项 6：单元测试通过

`pytest target_service/tests/ -q` 必须全部通过，且覆盖以下关键路径：
- SQL 参数化行为（注入尝试被正确拒绝）
- PII 脱敏函数输入输出
- 审计日志写入
- 合规策略的单元测试

---

## 禁止项

- 不得为了通过验收而删除业务功能
- 不得关闭审计中间件或降低日志级别
- 不得把敏感字段（`id_card`、`name`）写入非受控日志
- 不得把 PII 字段用于日志/异常消息的直接拼接

---

## 完成后的产出

1. `app/services/query_service.py` 全部 SQL 参数化
2. `app/core/security.py::mask_pii()` 实现并被所有相关 endpoint 调用
3. `app/middleware/audit_log.py::AuditLogMiddleware` 实现并在 `main.py` 注册
4. `app/core/sandbox_config.py`：沙箱策略（文件系统白名单、网络白名单）
5. `tests/`：新增合规相关测试，全部通过
6. `AUDIT_REPORT.md`：改造前后的对比报告，含各项验收的通过证据（日志片段、测试报告、静态扫描结果）

---

## 运行入口

```bash
# 1. 准备数据
python target_service/generate_sample_data.py

# 2. 启动 Agent 执行改造
python run.py

# 3. 验证验收
python verify.py
```
