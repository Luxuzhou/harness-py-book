# exp4: Pareto 前沿与 Shadow Testing

对应书稿 8.6（Shadow Testing）和 8.8（Pareto 前沿）。

## 实验文件

| 文件 | 作用 | 是否需 LLM |
|------|------|-----------|
| `run.py` | Pareto 分析：多配置 Accuracy × Cost 对比与前沿识别 | 是（Capture-only） |
| `pareto.py` | 读取结果，生成对比表和 matplotlib 图表 | 否 |
| `shadow_demo.py` | Shadow 差异比较：offline/live 双模式 | offline 否，live 是 |

## 最小验证

```powershell
# Pareto smoke（5 tasks x 1 seed，快速验证结构）
python run.py --smoke

# 生成 Pareto 图表
python pareto.py

# Shadow 离线模式（无 LLM）
python shadow_demo.py

# Shadow live 模式
python shadow_demo.py --live --smoke
```

## Pareto 前沿

四个配置（system_prompt v1/v2, tool_description v1/v2）在 (Accuracy, Cost) 平面上的分布。
位于前沿上的配置是"至少在一个维度上最优、且不被其他配置支配"的改动。
