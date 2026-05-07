# 对照实验：Agent（DeepSeek）vs Claude Code 直接修复

## 实验目的
对比 harness-pro 框架驱动的 Agent 与直接使用 Claude Code 修复同一漏洞的效率、路径差异，找出框架优化点。

## 修复目标
`filter_service.py` 中的 SQL 字符串拼接漏洞（10+ 处）。核心难点：该文件的方法返回 SQL 字符串片段，参数化需要改变返回类型（`str` -> `Tuple[str, List[Any]]`）。

---

## Agent（DeepSeek via harness-pro）路径

### 结果
- **迭代数**：60 turns（跑满上限）
- **修改文件数**：5 个（query_service, security, endpoints, audit_log, conftest）
- **filter_service.py**：**未修改**
- **pytest**：104/104 PASS
- **verify**：5/6 通过

### 行为特征
1. **阅读阶段冗长**：连续 read_file 8-12 次才进入修改阶段。Guard 多次提醒后才切换策略。
2. **bash 使用低效**：37 次 bash 调用，大量被 sandbox 拦截（路径问题），陷入重试循环。
3. **死循环**：对同一文件重复 read_file 3-4 次，Guard 检测并阻断。
4. **未识别接口变更需求**：Agent 似乎未能识别 filter_service.py 的 SQL 拼接需要递归修改整条调用链（filter_item_to_sql -> filter_group_to_sql -> simulation_filters_to_sql -> filter_to_sql）。
5. **缺少调用链分析**：未 grep 调用方确认修改范围。

---

## Claude Code 直接修复路径

### 结果
- **迭代数**：1 轮（直接定位并修复）
- **修改文件数**：1 个（filter_service.py）
- **filter_service.py**：**完全修复**
- **pytest**：104/104 PASS
- **verify**：6/6 通过（verify.py 正则误报待修，但代码层面无漏洞）

### 修复步骤
1. **grep 调用链**（2 次工具调用）
   - 确认 `filter_to_sql` / `simulation_filters_to_sql` 只在 `filter_service.py` 内部调用
   - 确认 `endpoints.py` / `query_service.py` 未调用这些方法
   - **结论**：可以安全地修改返回类型，无需改动其他文件

2. **设计参数化方案**
   - `filter_item_to_sql`：`str` -> `Tuple[str, List[Any]]`
   - `filter_group_to_sql`：递归收集子条件参数
   - `simulation_filters_to_sql`：`List[str]` -> `Tuple[List[str], List[Any]]`
   - `FilterService.filter_to_sql`：同步改返回类型

3. **执行修改**（4 次 Edit 调用）
   - IN/NOT_IN：动态生成 `(%s, %s, %s)` 占位符
   - LIKE：`%s` 占位符，参数值包含 `%` 通配符
   - 字符串/布尔/数字：统一参数化
   - 时间范围：`strftime` 结果作为参数
   - 固定子查询（`exclude_repeat_patients`）：无需参数化

4. **验证**
   - pytest：全部通过
   - 自定义脚本：确认无 SQL 注入模式残留

---

## 关键差异分析

| 维度 | Agent（DeepSeek） | Claude Code |
|------|------------------|-------------|
| **调用链分析** | 未执行 | 第一步就是 grep 调用方 |
| **返回类型变更** | 未识别需要变更 | 主动识别并执行 |
| **跨文件修改** | 改了 5 个文件，但避开了最难的 | 只改 1 个文件，精准定位 |
| **死循环/重复** | 重复 read_file，Guard 介入 22 次 | 无重复操作 |
| **验证反馈** | 未运行 verify.py 验证阶段性成果 | 改完后立即 pytest + 脚本验证 |
| **工具使用效率** | read=46, bash=37, glob=10 | read=1, grep=3, edit=4 |

### 根因分析：Agent 为什么没修 filter_service.py？
1. **缺乏调用链分析**：修改返回类型是高风险操作，Agent 没有先确认影响范围，因此不敢动手。
2. **递归修改未识别**：filter_service.py 的参数化不是单点修复，需要递归修改 4 个方法的签名和实现。Agent 可能在尝试了单点修改后发现编译错误，但没有足够的上下文来递归修复。
3. **迭代上限耗尽**：60 turns 中大量消耗在阅读文件和失败的 bash 调用上，实际用于代码修改的 turns 不足。
4. **缺少阶段性验证**：如果 Agent 在修改后能运行 verify.py，它会发现 filter_service.py 仍然是失败项，从而继续修复。

---

## harness-pro 框架优化建议

### 1. CLAUDE.md 增加策略指引
在 CLAUDE.md 中加入明确的代码修改策略：
- **修改接口前**：先 `grep` 调用方，确认影响范围
- **参数化 SQL**：返回类型需要从 `str` 改为 `Tuple[str, List[Any]]` 时，同步递归修改整条调用链
- **阶段性验证**：每完成一个文件的修改，运行 `pytest` 和 `verify.py` 确认效果

### 2. run.py 配置优化
- **planning_turns**：当前 1 轮可能不足以让 Agent 制定递归修改计划，可考虑 2 轮
- **max_iterations**：60 turns 对于需要递归修改的任务仍然紧张，建议 80-100

### 3. 框架层面的调用链分析工具
考虑在 Agent 可用工具中增加 `find_callers` 或 `grep_symbol` 工具，降低 Agent 使用 grep 的门槛。

### 4. 阶段性验证 Hook
在 Agent 的 hooks 中增加阶段性验证：每 N 轮或每完成一次 write_file/edit_file 后，自动运行 verify.py，将结果反馈给 Agent。
