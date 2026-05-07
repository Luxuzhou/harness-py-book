# Ch10 实验索引

## `hooks_defense/`

对应书稿 10.3 节"沙箱-Hook-CLAUDE.md 三层防御设计"以及 10.3.2 / 10.5.2 / 10.7.1 /
10.7.3 的相关章节。

### 包含的实验

1. **企业框架三轮递进**（`run_hooks_experiment.py`）
   - 无 Hook → Agent 读到完整 PII，能访问 .env
   - PreToolUse Hook → 拦截 .env 访问 + 危险命令
   - Pre + PostToolUse → 拦截 + PII 自动脱敏

2. **Claude Code 原生 Hooks**（`claude_hooks/` 子目录）
   - Shell 脚本 + settings.json 的实现方式
   - 对比企业框架版本，说明两种路径的取舍

### 复现命令

```bash
cd experiments/ch10/exp1_hooks_defense
python run_hooks_experiment.py
```

详见该目录下的 `README.md`。

## Harness 内核必须被实验捕获

第 10 章的重点不是"加一个脱敏函数"，而是三层防御是否真正形成闭环：

- **规则层**：CLAUDE.md 明确 SQL 参数化、PII 最小化、审计字段和导出策略。
- **Hook 层**：pre-hook 拦截 SQL 拼接、危险命令和外网访问；post-hook 在 session 落盘前脱敏，并对敏感路径 `fail-closed`。
- **沙箱层**：`network_isolated=True`，`sample_data/` 配置为只读路径，Agent 只能在 `target_service/` 内工作。
- **验证层**：`verify.py` 覆盖 SQL 参数化、mask_pii、审计中间件、网络隔离和 pytest。
- **观测层**：报告必须保存 hook warnings、sandbox blocks、session id、verify 输出，证明不是 prompt 自觉，而是代码约束生效。

离线检查：

```bash
python experiments/check_ch09_ch12_kernel.py
```

## 历史命名

本目录最初从 `experiments/hooks_article/`（公众号文章版）迁入并改名 `hooks_defense`，
2026-04 在书稿增设 Ch8《反馈调节》后从 `experiments/ch09/` 顺延到 `experiments/ch10/`，
对应新 Ch10"实战二：医疗数据服务的合规加固"。
