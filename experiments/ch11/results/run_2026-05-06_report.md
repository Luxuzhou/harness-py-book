# 第11章 多Agent编排实验报告

**实验时间**: 2026-05-06
**模型**: deepseek-chat (DeepSeek-V3)
**总耗时**: ~9分钟 (547秒 wall time)
**总成本**: ~$0.56 USD (约 4.0 元人民币)

## 实验配置

- 4 Agent: Architect / JavaDeveloper / PythonDeveloper / QAEngineer
- 5轮编排: Plan -> Dev(并行) -> QA -> Fix(并行) -> QA
- JavaDeveloper cwd: cases/refactor_enterprise/target_project/
- PythonDeveloper cwd: cases/data_compliance/target_service/

## 执行结果

| 轮次 | 角色 | Turns | Tools | 失败 | Tokens | Cost | 时长 | Guard介入 | Stop Reason |
|------|------|-------|-------|------|--------|------|------|-----------|-------------|
| R1 | Architect | 12 | 25 | 11 | 200,466 | $0.055 | 108s | 3 | max_iterations |
| R2 | JavaDeveloper | 20 | 37 | 10 | 406,196 | $0.112 | 96s | 2 | max_iterations |
| R2 | PythonDeveloper | 20 | 42 | 18 | 314,817 | $0.087 | 87s | 16 | max_iterations |
| R3 | QAEngineer | 15 | 24 | 13 | 234,854 | $0.065 | 61s | 2 | max_iterations |
| R4 | JavaDeveloper | 20 | 44 | **44** | 211,199 | $0.059 | 97s | **40** | max_iterations |
| R4 | PythonDeveloper | 20 | 40 | 7 | 447,296 | $0.123 | 86s | 0 | max_iterations |
| R5 | QAEngineer | 15 | 27 | 13 | 220,136 | $0.061 | 63s | 5 | max_iterations |
| **合计** | - | **122** | **239** | **116** | **2,034,964** | **$0.56** | **598s** | **68** | max_rounds (5) |

## 关键发现

### 1. 产物缺失：implementation_plan.md 与 test_report.md 未生成

- Architect 耗尽12次迭代仍未完成规划文档编写
- glob_search 被 sandbox 拦截（路径含 `..`）导致无法定位目标文件
- QA 同样未生成 test_report.md

**书稿支撑**: 11.5.1 节 — plan质量决定全局上限。实验证实如果Architect无法在预算内完成plan，后续所有Developer都在"无计划盲飞"。

### 2. JavaDeveloper Round 4 完全崩溃

- 44次工具调用全部失败（100%错误率）
- 40次Guard介入（死循环检测+连续失败告警）
- 陷入 read_file 死循环：反复读取相同文件14次以上

**书稿支撑**: 11.7.2 节 — QA发现问题后Developer自动修复的边界。实验证明当测试报告不存在或Agent无法理解失败根因时，修复轮不仅不能修复问题，反而会让Agent陷入更深的死循环。

### 3. PythonDeveloper 的压缩风暴

- Round 2: 11次压缩，节省92,833 tokens
- 反复读取大量文件导致上下文迅速膨胀至70%阈值
- Round 4表现反而更好（仅1次压缩），说明上下文管理有改善

**书稿支撑**: 11.5.2 节 — 字段命名不一致上下文压力。PythonDeveloper的高压缩次数说明跨项目文件读取确实带来了巨大的上下文负担。

### 4. 文件系统隔离生效但过度

Developer Agents 多次尝试读取编排目录下的 spec 文件：
- `cases/multiagent_enterprise/spec/api_contract.yaml`
- `cases/multiagent_enterprise/spec/requirement.md`
- `cases/multiagent_enterprise/spec/architecture.md`

全部被 SANDBOX 拦截。契约内容已通过 role_prompt 注入，但Agent仍本能地试图读取原始文件确认。

**书稿支撑**: 11.7.1 节 — cwd配置与路径隔离。实验验证了文件系统隔离确实阻止了越界访问，但也暴露了"prompt注入的契约 vs Agent主动读取的契约"之间的张力。

### 5. bash 命令100%被拦截

所有 Developer 的 bash 调用（`mvn compile`, `mvn test`, `pytest` 等）全部被 sandbox 拦截：
- "command contains parent-directory traversal"
- "absolute path not allowed"

这是 sandbox 安全策略的过度保护，Agent 无法理解为什么不能运行编译命令。

**书稿支撑**: 11.2.3 节 — Developer的bash权限限制。实验验证了bash限制的必要性，但也发现当前sandbox实现过于严格，连合法的 `mvn compile` 都被拦截。

### 6. 成本对比验证

| 方案 | 估算成本 | 本实验实际 |
|------|---------|-----------|
| Anthropic Solo $9 | 不可用 | - |
| Anthropic Multi $200 | 可用 | - |
| DeepSeek 四Agent | 书稿估 $0.3-0.5 | **$0.56** |

DeepSeek上的四Agent成本约0.56美元（约4元人民币），与书稿估算一致。成本差异主要来自模型定价（DeepSeek vs Claude），而非架构本身。

## verify.py 验证结果

- 4/7 通过（与运行前相同）
- FAIL: 接口契约一致性、Architect Plan、QA测试报告
- 原因：Agent未成功生成 implementation_plan.md 和 test_report.md

## 代码修复记录

本次实验前修复了以下代码问题：

1. `harness_py_pro/swarm.py`: AgentRole 添加 `sandbox_mode`, `network_isolated`, `allowed_paths`, `read_only_paths`, `filesystem_roots`
2. `harness_py_pro/swarm.py`: orchestrate() 添加 `round_plan` 参数支持
3. `harness_py_pro/swarm.py`: orchestrate() 和 run_pipeline() 中将 AgentRole 权限字段映射到 AgentConfig
4. `harness_py_pro/config.py`: AgentConfig 添加 `read_only_paths` 字段
5. `harness_py_pro/engine.py`: 创建 sandbox 时传递 `read_only_paths`

## 书稿写作建议

1. **11.5.1 节**: 可引用 Architect 12 turns / 200K tokens 仍未完成 plan 的数据，说明 plan 质量确实是全局瓶颈
2. **11.5.3 节**: 可引用 JavaDeveloper Round 4 的 44/44 工具失败作为"修复轮恶化"的典型案例
3. **11.5.4 节**: 可用 $0.56 实际成本数据替代估算值
4. **11.7.1 节**: 可用 Developer 试图读取 spec 文件被拦截的案例，说明路径隔离的双刃剑效应
5. **11.7.2 节**: 可用 PythonDeveloper 的 11 次压缩/Guard 16 次介入说明死循环检测的重要性
