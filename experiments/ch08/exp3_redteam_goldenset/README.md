# Exp3: Red Team Golden Set

对应书稿 8.7.5：Red Team Agent。

本实验用 26 条对抗任务比较 `baseline` 与 `defense` 两个 system prompt 版本的攻击成功率。prompt 版本通过 `AgentConfig.system_prompt_append` 注入，和真实规则注入路径一致。

## 任务类型

- `prompt_injection`
- `privilege_escalation`
- `pii_leak`

每条任务包含 `user_prompt`、`attack_class`、`success_signal` 和 `defense_target`。

## 运行

```powershell
python -B experiments/ch08/exp3_redteam_goldenset/run.py --help
python -B experiments/ch08/exp3_redteam_goldenset/run.py --smoke --version all
python -B experiments/ch08/exp3_redteam_goldenset/run.py --classes prompt_injection --version defense
```

完整实验需要模型 API。脚本真实执行只读工具，写入/执行类工具使用 capture-only 模拟，避免污染工作区。

## 输出

- `results/raw_<prompt_version>.jsonl`
- `results/intercept_rate.json`

## 工程要点

Red Team 不是为了证明 prompt 足够安全，而是作为发布硬门禁。只要 defense 版本引入新的逃逸路径，候选规则就不能进入 Canary。
