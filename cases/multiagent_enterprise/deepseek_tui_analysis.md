# DeepSeek-TUI 多 Agent 架构分析

## 核心设计原则

### 1. 委托一切给子代理 (Delegate Everything to Sub-agents)
- **父代理 = 协调者**：只做决策和分发，不直接执行具体任务
- **子代理 = 执行者**：每个子代理拥有独立的会话上下文（fresh session）
- **关键优势**：子代理的上下文不会污染父代理，避免 session 膨胀和循环

### 2. 三层防护防止循环

#### 2.1 LoopGuard（工具调用级）
```rust
const IDENTICAL_CALL_BLOCK_THRESHOLD: u32 = 3;  // 相同参数调用超过3次直接阻断
const FAILURE_WARN_THRESHOLD: u32 = 3;             // 连续失败3次警告
const FAILURE_HALT_THRESHOLD: u32 = 8;             // 连续失败8次强制停止
```
- **相同调用阻断**：基于参数哈希，第3次相同调用被阻断并返回错误
- **失败递增**：连续失败会累积，成功则重置计数器
- **Paginated reads 安全**：不同 offset 的调用参数不同，不会被误判

#### 2.2 TurnContext 步数限制（回合级）
```rust
const DEFAULT_MAX_STEPS: u32 = 100;
fn at_max_steps(&self) -> bool { self.step >= self.max_steps }
```
- 每个 turn（一次用户请求的处理）最多 100 步
- 每执行一轮工具调用，`turn.next_step()` 递增
- 达到上限后直接 `break` 退出循环

#### 2.3 Capacity Controller（系统级）
```rust
enum GuardrailAction {
    NoIntervention,
    TargetedContextRefresh,  // 针对性压缩上下文
    VerifyWithToolReplay,    // 重放验证工具调用
    VerifyAndReplan,         // 清空上下文，从规范状态重新规划
}
```
- 监控：turn 数、工具调用数、上下文使用比例、唯一引用数
- 风险分级：Low / Medium / High / Critical
- 干预措施：上下文压缩 → 重放验证 → 强制重规划

### 3. 子代理运行时设计

```rust
async fn run_subagent_loop(
    agent_id: String,
    agent_type: SubAgentType,
    prompt: String,
    assignment: SubAgentAssignment,
    allowed_tools: Option<Vec<String>>,  // 工具白名单
    max_steps: u32,                       // 步数上限
    ...
) -> Result<SubAgentResult> {
    for _step in 0..max_steps {
        // 1. 检查取消信号
        if runtime.cancel_token.is_cancelled() { ... }

        // 2. 请求模型响应（非流式，带 120s 超时）
        let response = tokio::time::timeout(
            STEP_API_TIMEOUT,
            runtime.client.create_message(request)
        ).await;

        // 3. 执行工具调用（带 30s 超时）
        for (tool_id, tool_name, tool_input) in tool_uses {
            let result = tokio::time::timeout(
                TOOL_TIMEOUT,
                tool_registry.execute(&agent_id, &tool_name, tool_input)
            ).await;
        }

        // 4. 无工具调用则完成
        if tool_uses.is_empty() { break; }
    }
}
```

### 4. 并行工具执行
- **只读工具**（read_only）可以并行执行
- **写入工具**必须串行执行
- 通过 `should_parallelize_tool_batch(&plans)` 判断

### 5. 上下文管理
- **自动压缩**：当上下文超过阈值时自动触发 compaction
- **工作集（Working Set）**：跟踪最近访问的文件和路径，优先保留
- **规范状态（Canonical State）**：capacity controller 清空上下文时保留的精简状态
  - Goal（目标）
  - Constraints（约束）
  - Confirmed Facts（已确认事实）
  - Open Loops（未完成项）
  - Pending Actions（待执行动作）

## 与 harness_py_pro 的对比

| 特性 | DeepSeek-TUI | harness_py_pro (当前) |
|------|-------------|----------------------|
| 子代理 | 支持，fresh session | 不支持，共享 session |
| LoopGuard | 阻断 + 警告 + 停止 | 仅警告 |
| 步数限制 | 100步/turn | 无 |
| 容量控制 | 风险分级 + 主动干预 | 无 |
| 工具超时 | 30s 工具 / 120s API | 无 |
| 并行执行 | 只读工具并行 | 无 |
| 上下文压缩 | 自动 + 规范状态恢复 | 手动触发 |
| 工具白名单 | 子代理可限制工具集 | 支持 tool_filter |

## 可借鉴的优化点

### 高优先级
1. **LoopGuard 增强**：从"仅警告"升级为"阻断相同调用 + 强制停止"
2. **硬步数限制**：为每个 agent 的 turn 设置 max_steps（如 30-50 步）
3. **子代理会话隔离**：spawn 的 agent 使用独立 message history

### 中优先级
4. **工具调用超时**：防止无限等待（如 60s 工具 / 180s API）
5. **并行只读工具**：batch 执行 grep/read 等只读操作
6. **Capacity 监控**：监控步数、错误率、上下文大小，触发干预

### 低优先级
7. **规范状态恢复**：循环严重时清空上下文，保留关键事实重规划
8. **工作集追踪**：记录最近访问文件，优先保留在上下文中
