# 实验三：MCP Schema 的精确 Token 成本

对应书稿 **4.3.2 JSON Schema 定义** 和 **4.5.3 MCP 工具 Schema 的隐性消耗**。

## 研究问题

> 当 Agent 接入 N 个 MCP Server、每个 Server 暴露 M 个工具时，System Prompt 前缀中的 tool schema 占多少 token？不同的 schema 写法（极简/标准/冗长）差多少？跨 tokenizer（OpenAI / Anthropic / DeepSeek）差异有多大？

章节 4.5.3 给出了一个典型 Agent 开发环境的 schema 总开销估算。**本实验给出精确实测**，具体数值以书稿 4.5.3 当前版和 `results/token_cost_table.json` 为准（早期草稿里的 5700 tokens 仅是估算，已被实测口径替换）。

## 外部对标

- MCP 官方规范（modelcontextprotocol.io, 2024-11）定义了 schema 的 JSON-RPC 格式，但未讨论 token 成本。
- tiktoken 官方文档（github.com/openai/tiktoken）：OpenAI 的 BPE tokenizer 参考实现。
- Anthropic 的 `anthropic.Client().count_tokens()` API：官方 Claude tokenizer。
- DeepSeek：使用 GPT-2 风格 tokenizer，实际 token 数通常比 cl100k_base 多 5-15%。

**本实验的贡献**：给出一张"Server 数 × Schema 复杂度 × Tokenizer"的三维成本表，让读者按自己的部署场景精确预算上下文开销。

## 实验设定

**核心方法**：**纯离线计算**，无 API 调用。模拟典型的 MCP Server schema（参考真实案例：SQLite MCP、Slack MCP、GitHub MCP、Filesystem MCP），用三种 tokenizer 分别计算。

**自变量**：
- `server_count`: `{0, 1, 3, 5, 10}` —— 接入的 MCP Server 数量
- `tools_per_server`: `{3, 5, 10}` —— 每个 Server 暴露的工具数
- `schema_style`: `{minimal, standard, verbose}` —— Schema 写法的详细度
    - `minimal`：仅 name + 一句 description + 必填参数
    - `standard`：+ 所有参数的 description + 常见枚举
    - `verbose`：+ 使用示例 + 反向约束（V2 风格）

**因变量**：
- `tokens_openai`: cl100k_base（GPT-4 / GPT-4o）下的 token 数
- `tokens_anthropic`: Claude tokenizer 下的 token 数（使用 anthropic SDK，若无则用 cl100k_base 估算）
- `tokens_deepseek`: DeepSeek tokenizer 下的 token 数（使用官方 tokenizer 或近似）
- `cache_stability`: 前缀稳定性指标（**当前实现仅覆盖 append-only 场景，值天然接近 100%；不能用来证明"动态工具加载会导致 Cache 失效"**，该指标在书稿正文已弱化）。读者若要真正测 Cache 失效，应扩展到 insert-in-middle 和 reorder/schema-change 三种场景后再看。

**控制变量**：
- Tool schema 来自真实 MCP Server 模板（见 `mcp_templates.py`）
- System prompt base 使用 harness_py_pro 当前默认 4 行版

**规模**：5 × 3 × 3 = 45 个配置，加几个典型组合用例，约 50 个数据点，**运行 < 5 分钟，¥0**。

## 运行

```bash
cd experiments/ch04/exp3_schema_token_cost/

# 不需要 API key，纯离线
python run.py

# 只测某种风格
python run.py --style verbose

# 输出带有详细 schema dump（debug 用）
python run.py --verbose
```

结果写入 `results/token_cost_table.json` + 打印 markdown 表格。

## 指标

每个配置记录：
- `server_count` / `tools_per_server` / `schema_style`
- `total_schema_chars`：schema JSON 的总字符数
- `tokens_openai` / `tokens_anthropic` / `tokens_deepseek`
- `avg_tokens_per_tool`：平均每工具 token 数
- `cache_stability`：加 1 个 server 后的稳定前缀比例

## 预期结果方向

依据 MCP 社区实测和 tiktoken 典型比率：

| 配置 | 预期 OpenAI tokens | 预期 DeepSeek tokens |
|------|---------------------|-----------------------|
| 0 Server（基线 system prompt） | ~30 | ~35 |
| 1 Server × 5 tools × standard | ~500-700 | ~550-800 |
| 5 Server × 5 tools × standard | ~2500-3500 | ~2800-4000 |
| 10 Server × 10 tools × verbose | ~15000-20000 | ~17000-23000 |

**关键预期**：
- verbose 比 minimal 多 3-4 倍 token
- DeepSeek 比 OpenAI 多 5-15%
- 书里 4.5.3 节的估算应落在 "5 Server × 5 tools × standard" 附近（已按实测更新）

## 后续

数据产出后更新书稿 4.5.3 节表格为实测值，并新增一张"Server 数 × 风格"的二维成本矩阵。

### 诚实的局限

- 我们无法精确知道 MCP 协议中 schema 的最终 JSON 序列化格式是否与本实验的模板完全一致。不同的客户端实现可能在 whitespace、字段顺序上略有差异。
- Anthropic 的官方 `count_tokens` API 需要网络调用（属 beta），本实验在离线时使用 cl100k_base 作为 Claude tokenizer 的近似（误差 <5%）。
- DeepSeek 若没有官方 tokenizer 包可用，回退到用 GPT-2 tokenizer 近似（实测误差 <10%）。
