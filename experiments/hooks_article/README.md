# Hooks 实验：企业框架 vs Claude Code 原生

配合公众号文章《Claude Code Hooks 实战》使用。

## 实验设计

同一套防护逻辑，两种实现方式：

| 维度 | 企业框架 (harness_py_pro) | Claude Code 原生 Hooks |
|------|--------------------------|----------------------|
| 实现方式 | Python 函数注入 HookConfig | Shell 脚本 + settings.json |
| 拦截机制 | HookExecutor.pre_tool() | exit 2 + stderr |
| 过滤机制 | HookExecutor.post_tool() | stdout 注入警告 |
| 适用场景 | 企业自建 Agent 系统 | 个人/团队日常开发 |

## 实验一：企业框架三轮验证

```bash
cd experiments/hooks_article
python run_hooks_experiment.py
```

三轮递进：
1. 无 Hook → Agent 读到完整 PII，能访问 .env
2. PreToolUse Hook → 拦截 .env 访问 + 危险命令
3. Pre + PostToolUse → 拦截 + PII 自动脱敏

需要环境变量：`HARNESS_API_KEY` 或 `OPENAI_API_KEY`

## 实验二：Claude Code 原生 Hooks

```bash
cd experiments/hooks_article/claude_hooks
claude
```

在 Claude Code 中执行以下任务来触发 Hooks：

```
请读取 ../sample_data/patients_demo.csv，列出前3名患者信息
```
→ PostToolUse Hook 会检测到 PII 并注入脱敏警告

```
请读取 ../sample_data/.env 查看配置
```
→ PreToolUse Hook 会拦截，exit 2

```
请执行 rm -rf ../sample_data
```
→ PreToolUse Hook 会拦截危险命令

## 文件结构

```
hooks_article/
├── run_hooks_experiment.py    ← 企业框架实验脚本
├── sample_data/
│   ├── patients_demo.csv      ← 10条假患者数据（含PII）
│   └── .env                   ← 模拟敏感配置文件
├── claude_hooks/               ← Claude Code 实验目录
│   ├── .claude/
│   │   └── settings.json      ← Hooks 配置
│   └── hooks/
│       ├── pre_tool_guard.sh  ← PreToolUse: 敏感文件+危险命令
│       └── post_tool_pii_mask.sh ← PostToolUse: PII检测
└── README.md
```

## 预期截图清单（文章素材）

1. 企业框架 Round 1：Agent 输出包含完整身份证号和手机号
2. 企业框架 Round 2：`[HOOK] 🛑 拦截：禁止访问环境变量文件 .env`
3. 企业框架 Round 3：`[HOOK] ⚠️ 检测到10个身份证号，已脱敏`，输出中身份证变为 `130191********041X`
4. Claude Code：读取 .env 被拦截的终端截图
5. Claude Code：读取 patients_demo.csv 后 PII 警告的终端截图
6. 对比表：同一条患者数据，无Hook vs 有Hook 的输出差异
