# 实验二：Cache 前缀稳定性敏感度

## 目的

对应书稿 5.4.3 节"DeepSeek 与通义千问的 Cache 支持"与 5.5.2 节
"前缀变动导致 Cache 全量失效"。

测量 system prompt 不同程度的"污染"对 DeepSeek 自动缓存命中率的实际影响。
用实测数据替代章节里的经验值（如"第2轮后应稳定在85%以上"）。

## 五种配置与实测命中率（2026-04，DeepSeek-V3，30 轮/配置）

| 配置 | 污染点 | 实测命中率均值（2 轮后） |
|------|--------|---------------------|
| A 规范版 | 无。system prompt 完全静态，动态信息在 user message | **88.6%** |
| D 小时级时间戳 | system prompt 开头含小时级时间戳 | **89.0%**（与 A 几乎无差异） |
| E schema 乱序 | system prompt 不变，但每轮 tools 列表随机排序 | **82.9%**（末尾乱序损失约 6pp） |
| B 秒级时间戳 | system prompt 开头含秒级时间戳 | **0.0%**（开头首字节即失效） |
| C Request-ID | system prompt 开头嵌入 uuid4 | **0.0%**（开头首字节即失效） |

DeepSeek 的缓存基于请求前缀的重叠匹配，任何前缀变动都会让匹配从变动点起断裂。
五种配置系统性地覆盖"完全稳定"到"前缀首字节即变动"的光谱。

## 变量

- **轮数**：默认30轮/配置，足以看出命中率的稳态
- **任务**：每轮让模型分析一个不同的 Python 源文件片段（5个样本循环使用），
  避免轮次间状态依赖；同时任务类型固定（"Analyze this file"），
  保证 user message 结构的一致性
- **模型**：`deepseek-chat`，temperature=0.0，最小化输出差异
- **间隔**：默认1.5秒，避免触发频控，也防止缓存 TTL 内的相互干扰

## 指标

从 DeepSeek 的 `usage` 字段读取：

- `prompt_cache_hit_tokens`：命中缓存的输入 token 数
- `prompt_cache_miss_tokens`：未命中的输入 token 数
- 命中率 = `hit / (hit + miss) * 100%`

每轮记录上述三个值到 `results/results.json`，不生成图表文件；读者若要可视化，可基于 `results.json` 自行绘制"轮次 vs 命中率"折线图。

## 运行

```bash
# 冒烟（2配置×3轮，验证管道）
python run.py --smoke

# 全量（5配置×30轮，约25分钟）
python run.py

# 只跑特定配置
python run.py --configs A,B,C --rounds 20

# 间隔调整（默认1.5秒）
python run.py --sleep 2.0
```

结果增量写入 `results/results.json`，每轮即落盘，中途失败不丢数据。

## 实际产出

- `results/results.json`：每轮的原始 usage 数据（5 配置 × 30 轮 = 150 次）
- 当前仓库只保留 `results.json` 作为数据落盘；`plot.py` 与图文件未生成，读者如需可视化可基于 `results.json` 自行绘制

## 成本估算

按 DeepSeek 2026-04 定价（$0.27/M 未命中 input, $0.07/M 命中）：
- 每轮约 4K input + 200 output tokens
- 30轮 × 5配置 = 600K input + 30K output
- 不含缓存成本上限约 $0.17
- 实际（因为有缓存命中）通常 $0.10 以内

## 关键结论

**Cache 命中率的敏感度是空间的，不是时间的**：开头一字节变化彻底破坏缓存，末尾整段重排只损失部分。

- A vs B/C：秒级时间戳 / 随机 UUID 污染 system prompt 开头 → 命中率从 88.6% 断崖跌到 0.0%
- A vs D：把时间精度降到小时级 → 命中率回到 89.0%，与完全静态几乎无差异
- A vs E：工具 schema 每轮随机重排 → 损失 6pp，不是一些工程博客说的"30% 衰减"（因为 schema 在 system prompt 末尾）

数据已回填书稿 5.4.3 / 5.5.2 / 5.5.4 节。
