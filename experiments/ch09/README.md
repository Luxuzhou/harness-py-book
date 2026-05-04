# Ch9 实验索引

对应书稿第 9 章《实战一：遗留系统代码重构》。

## 当前实验

| 编号 | 目录 | 对应章节 | 状态 | 一句话目标 |
|------|------|---------|------|-----------|
| exp1 | `exp1_refactor_metrics/` | 9.4 / 9.5 重构前后效果 | 骨架 + 离线门禁 | 量化重构前后的代码异味数、God Service 行数、cyclomatic complexity、测试覆盖率 |

## Harness 内核必须被实验捕获

第 9 章不能只比较"Agent 有没有改完"。实验报告必须同时记录这些 Harness 控制点：

- **规划门禁**：`planning_turns=5` 时，前 5 轮只暴露只读工具。
- **权限边界**：`allowed_paths` 把 Agent 限定在 `target_project/`；Hook 只允许 service/test/controller wiring 的必要修改。
- **验证门禁**：`verify.py` 同时检查 API 契约、Controller 依赖倒置、测试、编译/语法、越权变更。
- **回归证据**：before/after metrics 不能替代验收脚本；必须把 `verify.py` 输出和 session id 一起保存。
- **反馈输入**：失败项要回写到下一轮 CLAUDE.md/TASK.md，而不是只在正文里复盘。

离线检查：

```bash
python experiments/check_ch09_ch12_kernel.py
```

## 与 cases/refactor_enterprise 的关系

`cases/refactor_enterprise/target_project/` 是被重构的目标 Java 项目。本实验的
作用是给这个 case 提供"前后对照数据"——book 章节里"$0.29 / 40 轮 / 12 分钟"
讲的是过程，本实验的"重构前 1266 行 God Service → 重构后 N 行"讲的是结果。

跑实验的标准流程：

1. `git stash` 或 `git checkout` 到重构前的 commit，对 target_project/ 跑一次 metrics
2. 跑 `cases/refactor_enterprise/run.py` 让 Agent 完成重构
3. 对重构后的 target_project/ 再跑一次 metrics
4. 输出 before/after 对照表
