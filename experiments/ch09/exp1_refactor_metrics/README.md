# 实验 1：重构前后量化对照

对应书稿 **9.4 重构方案设计与执行** 与 **9.5 五项验收**。

## 研究问题

第 9 章正文有大量过程数据（轮数、成本、耗时），但缺一个最关键的"结果数据"：
重构前后的代码质量到底改善了多少？

> 给定 `cases/refactor_enterprise/target_project/` 这个 7929 行 Java 项目，
> Agent 完成重构后，下面 5 个量化指标分别变化了多少？

## 度量指标

| 指标 | 工具 | 期望方向 |
|------|------|---------|
| 总行数 LOC | `cloc` 或 `find + wc` | ↓（少量减少，重构应抽出冗余） |
| God Service 行数（CpPlanService） | 简单 wc | ↓ 显著（章节断言 1266 → 拆成多个 <300 行的服务） |
| 平均方法长度 | 用 javaparser 或 grep 估算 | ↓（God 类拆开后单方法更短） |
| Cyclomatic Complexity 平均值 | PMD / SonarQube CLI | ↓（拆分降低复杂度） |
| PMD 警告数（基础规则集） | PMD | ↓（章节断言 SQL 注入、混合注入风格等异味被消除） |
| 测试覆盖率（line） | JaCoCo（如有 mvn test） | ↑（重构应保持或提升） |

## 设计

```
[ 重构前 quick metrics ]
       │
       ▼
[ Agent 跑完 cases/refactor_enterprise/run.py ]
       │
       ▼
[ 重构后 quick metrics ]
       │
       ▼
[ before/after 对照表 + Δ 百分比 ]
```

**两种运行模式**：

- `python run.py before`：在当前 working tree 上算一次 metrics，写入 `results/before.json`
- `python run.py after`：同样算一次，写入 `results/after.json`
- `python compare.py`：对比 before / after，输出 markdown 表

**实施约束**：
- 假设 `cloc` 可用（轻量）；如不可用退化为 `find + wc -l`
- PMD 静态分析为可选（需要装 PMD 或 SonarQube CLI），缺失时跳过 PMD 列
- 测试覆盖率为可选（需要 mvn + jacoco），缺失时跳过

## 预期产出

- `results/before.json`：重构前的指标快照
- `results/after.json`：重构后的指标快照
- `results/comparison.md`：可贴入 9.5 节的对照表
- `results/figures/before_after.png`：5 个指标的双柱状对比

## 复现命令

```bash
# 0. 准备：保证 target_project/ 处于"重构前"状态（git checkout 到对应 commit）

# 1. 算重构前 metrics
python run.py before

# 2. 跑 case 让 Agent 重构
cd ../../cases/refactor_enterprise && python run.py
cd -

# 3. 算重构后 metrics
python run.py after

# 4. 生成对比报告
python compare.py
```

## 讨论框架（待数据回填）

1. **God Service 拆分有效**？1266 行 → 200 行 × N 个服务，平均方法长度 ↓
2. **PMD 警告数下降**？章节断言"SQL 注入修复"、"混合注入风格统一"，PMD 应该体现
3. **测试覆盖率保持或提升**？重构最大的风险是"重构破坏行为"——覆盖率不下降是底线

## 限制

- 单次实验，没有 multi-seed（每次 Agent 跑结果略不同）
- PMD / JaCoCo 都是工具性指标，不能直接反映"业务可读性"
- 跨语言适配性差：本实验只针对 Java；Ch10 Python 案例可类似搭一个独立实验
