# harness_py_pro 框架优化方案

基于 DeepSeek-TUI 架构分析，针对多 Agent 实验中的循环问题，提出以下可落地的优化。

---

## 问题诊断

### 根本原因：模型缺乏自主"规划-执行"切换能力
- deepseek-chat 在收到复杂任务后，会陷入"搜索→读取→搜索→读取"的无限循环
- 没有外部强制力时，模型不会主动停止探索、提交成果
- 人类演示成功的原因是：人类作为 orchestrator 强制切换了 phase

### 当前框架的防护缺口
1. **LoopGuard 只警告不阻断** — 模型收到警告后可能忽略继续循环
2. **无硬步数限制** — `max_iterations=15` 是软性建议，工具调用次数无上限
3. **无 phase 锁定** — 规划阶段结束后模型仍可能回到搜索模式
4. **会话共享** — 所有 Agent 共享同一 message history，上下文污染严重

---

## 优化方案（按优先级排序）

### P0: LoopGuard 强制阻断（1-2 小时实现）

**目标**：将 LoopGuard 从"提醒"升级为"强制执行"

**修改 `loop_guard.py`**：

```python
@dataclass
class LoopGuard:
    max_identical_calls: int = 3        # 第3次相同调用阻断
    max_consecutive_errors: int = 3     # 从5降到3，与TUI对齐
    max_same_tool_streak: int = 6       # 从8降到6
    max_total_tool_calls: int = 100     # 从200降到100

    # 新增：强制停止阈值
    halt_after_interventions: int = 3   # 累计3次介入后强制停止

    def check(self, tool_name, tool_args, success, result_preview):
        # ... 现有检测逻辑 ...

        # 强制停止：如果已经介入过多次，直接返回 halt 信号
        if self._intervention_count >= self.halt_after_interventions:
            return 'halt', (
                f'强制停止：LoopGuard 已介入 {self._intervention_count} 次，'
                f'判定为无法收敛的死循环。请提交当前已有成果并结束任务。'
            )

        # 现有逻辑返回 (intervene, message) ...
```

**修改 `engine.py`**：

```python
# 在 LoopGuard 检查处
intervene, guard_msg = guard.check(tool_name, tool_args, ok, tool_content[:200])

if intervene == 'halt':
    # 强制停止整个 run
    result.stop_reason = f'loop_guard_halt: {guard_msg}'
    result.output = content or f'[被LoopGuard强制停止] {guard_msg}'
    break  # 跳出主循环

elif intervene:
    # 原有的提醒逻辑
    messages.append({
        'role': 'user',
        'content': f'<system-reminder>[LOOP GUARD] {guard_msg}</system-reminder>',
    })
```

**预期效果**：Agent 在循环 3 次后被强制停止，避免无限消耗 token。

---

### P0: 硬步数限制 + Phase 工具锁定（2-3 小时实现）

**目标**：每个 phase 有明确的步数上限和可用工具集

**修改 `config.py` 的 AgentConfig**：

```python
@dataclass
class AgentConfig:
    # ... 现有字段 ...

    # Phase 配置
    planning_max_steps: int = 5         # 规划阶段最多5步（搜索+阅读）
    execution_max_steps: int = 20       # 执行阶段最多20步（编辑+测试）
    verification_max_steps: int = 5     # 验证阶段最多5步

    # Phase 工具白名单
    planning_tools: list[str] = field(
        default_factory=lambda: ['glob_search', 'grep_search', 'read_file']
    )
    execution_tools: list[str] = field(
        default_factory=lambda: ['write_file', 'edit_file', 'read_file', 'bash']
    )
```

**修改 `engine.py` 的主循环**：

```python
# 在 iteration 循环中
phase = _determine_phase(iteration, ac.planning_turns, result.tool_calls)
phase_max_steps = {
    'planning': ac.planning_max_steps,
    'execution': ac.execution_max_steps,
    'verification': ac.verification_max_steps,
}.get(phase, ac.max_iterations)

# Phase 步数检查
phase_steps = result.tool_calls_by_phase.get(phase, 0)
if phase_steps >= phase_max_steps:
    result.stop_reason = f'phase_limit: {phase} reached {phase_max_steps} steps'
    # 自动推进到下一阶段或结束
    if phase == 'planning':
        messages.append({
            'role': 'user',
            'content': f'<system-reminder>[PHASE LOCK] 规划阶段已达 {phase_max_steps} 步上限。'
                       f'停止搜索，立即基于已有信息开始执行。</system-reminder>',
        })
        # 强制进入 execution phase
        continue
    else:
        break

# 工具过滤：非当前 phase 的工具返回错误
def _filter_tools_by_phase(tool_calls, phase, ac):
    allowed = {
        'planning': ac.planning_tools,
        'execution': ac.execution_tools,
    }.get(phase)
    if not allowed:
        return tool_calls

    filtered = []
    for tc in tool_calls:
        name = tc.get('function', {}).get('name', '')
        if name in allowed:
            filtered.append(tc)
        else:
            # 返回错误结果给模型
            tc['__blocked'] = f'Tool "{name}" 不在 {phase} 阶段白名单中。可用: {allowed}'
    return filtered
```

**预期效果**：规划阶段最多搜索 5 次，之后必须开始执行，无法退回搜索模式。

---

### P1: 子代理会话隔离（4-6 小时实现）

**目标**：每个 Agent 有独立的 message history

**修改 `swarm.py` 的 `orchestrate()`**：

```python
def orchestrate(...):
    # ... 现有逻辑 ...

    for round_num in range(1, max_rounds + 1):
        for role in roles:
            # ...

            # 关键修改：每个 agent 使用 fresh session
            agent_result = run(
                agent_task,
                model_config=mc,
                agent_config=agent_config,
                completion_client=completion_client,
                verbose=verbose,
                # 新增：不继承父会话的 message history
                fresh_session=True,
            )

            # 将 agent 的产出写入文件，供后续 agent 读取
            output_file = work_dir / 'output' / f'{role.name}_round{round_num}.md'
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(agent_result.output, encoding='utf-8')
```

**修改 `engine.py` 的 `run()`**：

```python
def run(..., fresh_session: bool = False):
    # ...
    if fresh_session:
        # 只保留 system prompt 和当前 task
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': task},
        ]
    # ...
```

**预期效果**：每个 Agent 从零开始，不会累积前序 Agent 的循环历史。

---

### P1: 工具调用超时（1 小时实现）

**修改 `engine.py` 的工具执行**：

```python
import signal
from concurrent.futures import TimeoutError

def _execute_single_tool(..., timeout: int = 60):
    """执行单个工具，带超时保护。"""

    def timeout_handler(signum, frame):
        raise TimeoutError(f'Tool {tool_name} timed out after {timeout}s')

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)

    try:
        # ... 原有执行逻辑 ...
        ok, tool_content = registry.execute_tool(tool_name, tool_args, ac, turn=turn)
    except TimeoutError as e:
        ok, tool_content = False, str(e)
    finally:
        signal.alarm(0)

    return ok, tool_content
```

> Windows 下使用 `threading.Timer` 替代 `signal.SIGALRM`。

---

### P2: 容量监控 + 规范状态恢复（3-4 小时实现）

**新增 `capacity_controller.py`**：

```python
@dataclass
class CapacitySnapshot:
    turn_index: int
    tool_calls_recent: int      # 最近窗口工具调用数
    context_used_ratio: float   # 上下文使用比例
    consecutive_errors: int
    risk_band: str              # low / medium / high / critical

class CapacityController:
    def observe(self, messages, turn, guard_stats) -> CapacitySnapshot:
        # 计算风险指标
        # 返回风险分级

    def decide(self, snapshot) -> GuardrailAction:
        if snapshot.risk_band == 'critical':
            return GuardrailAction.VERIFY_AND_REPLAN
        if snapshot.risk_band == 'high':
            return GuardrailAction.TARGETED_COMPRESS
        return GuardrailAction.NO_INTERVENTION
```

**预期效果**：在上下文膨胀或错误累积时主动干预，避免 session 崩溃。

---

## 实施路线图

| 阶段 | 内容 | 预计时间 | 验证方式 |
|------|------|---------|---------|
| 1 | LoopGuard 强制阻断 + 硬步数限制 | 3 小时 | 单 Agent 循环测试 |
| 2 | Phase 工具锁定 | 2 小时 | 规划阶段不超5步 |
| 3 | 子代理会话隔离 | 4 小时 | 多 Agent 无上下文污染 |
| 4 | 工具超时 + 容量监控 | 3 小时 | 长耗时工具自动终止 |
| 5 | 端到端实验验证 | 2 小时 | run.py 7/7 通过 |

**总计：约 14 小时开发时间**

---

## 立即可做的最小改动（30 分钟）

如果希望先验证思路，可以只做以下改动：

1. **`loop_guard.py`**：将 `max_consecutive_errors` 从 5 改为 3，增加 `halt_after_interventions=2`
2. **`engine.py`**：在 `intervene=True` 时，如果 `_intervention_count >= 2`，直接 `break` 停止
3. **`swarm.py`**：将 `max_iterations` 从 15 改为 8（减少单 Agent 循环空间）

这三行改动即可显著改善循环问题，作为快速验证。
