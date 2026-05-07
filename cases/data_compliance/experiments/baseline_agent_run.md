# 实验 Baseline：harness-pro + DeepSeek Agent

## 实验配置
- 模型：deepseek-chat
- 迭代上限：60 turns（实际跑满 60 turns）
- 规划轮数：1
- Sandbox：bypass（中间发现 bypass 未真正生效，已修复框架 bug）
- 网络隔离：True
- Hooks：pre_tool（SQL 拼接拦截）+ post_tool（PII 脱敏）

## 改造结果
### 成功修改的文件（5/6 检查项通过）
1. **query_service.py** - SQL 参数化完成。所有 f-string SQL 改为 `%s` 参数化，新增 ORDER BY 白名单校验。
2. **security.py** - 新增 `mask_pii()` 函数，实现身份证/姓名/手机号脱敏。
3. **endpoints.py** - API 响应接入 `mask_pii()`。
4. **audit_log.py** - 审计中间件改为持久化写入（audit_logs/*.jsonl）。
5. **conftest.py** - 修复硬编码测试日期为 `date.today()`。

### 未完成的漏洞
- **filter_service.py** - 10+ 处 SQL 字符串拼接未修复（IN/LIKE/时间范围/性别等条件直接拼接）。

### 验证结果
- pytest：104/104 PASS
- verify.py：5/6 通过（SQL 参数化项因 filter_service.py 失败）

## Agent 行为特征（用于对照分析）
1. 阅读阶段：连续 read_file 8-12 次，Guard 多次提醒才切换策略。
2. 工具使用：read_file=46, bash=37, glob_search=10。bash 大量使用但多次被 sandbox 拦截（路径问题）。
3. 死循环：对同一文件重复 read_file 3-4 次，Guard 检测并阻断。
4. API 结构异常：assistant 调用 6 个 tool 后只返回 3 个 tool_result，导致紧急压缩。
5. 未修复原因推测：filter_service.py 的 SQL 拼接涉及返回类型变更（str -> Tuple[str, List]），Agent 未能识别需要递归修改整条调用链。
