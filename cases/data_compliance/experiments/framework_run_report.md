# 框架自主执行实验报告（Session: 7db260d56c14）

## 实验时间
2026-05-06

## 执行方式
harness-pro 框架自主运行（Agent + 沙箱 + Hook + CLAUDE.md）

## 核心指标

| 指标 | 数值 |
|------|------|
| 总轮数 | 63 turns |
| 工具调用 | 83 次（7 次错误） |
| Token 消耗 | 2,749,706 |
| API 费用 | ~$0.76 |
| 执行时长 | 490.9 秒（约 8.2 分钟） |
| 验收结果 | **6/6 全部通过** |
| Pytest | 104/104 PASS |

## 工具使用分布

| 工具 | 次数 |
|------|------|
| read_file | 34 |
| edit_file | 27 |
| bash | 10 |
| grep_search | 7 |
| todo_write | 4 |
| glob_search | 1 |

## 修改文件

- `filter_service.py` — 13 次编辑，参数化改造
- `query_service.py` — 14 次编辑，参数化改造
- `verify.py` — 修复正则误报

## 框架防御触发

- Hook 合规警告：8 条（PII 脱敏触发）
- Guard 介入：2 次（连续 read_file 超限）
- Token 压缩：1 次（节省 35,256 tokens）

## 关键时间线

| 时间点 | 事件 |
|--------|------|
| +12.6s | 首次成功读取文件 |
| +28.5s | 首次 bash 探索目录 |
| +116.8s | 首次 edit_file（开始改造） |
| +~300s | 完成核心参数化改造 |
| +490.9s | 全部验收通过 |

## 结论

框架在修复了 3 个关键 bug（沙箱 bypass 路径检查、args['path'] KeyError、cwd 设置）后，
能够自主完成全部 6 项合规改造任务。但执行过程中暴露了以下问题：

1. 需要 CLAUDE.md 的 3 条参数化规则来补偿 Agent 自主规划的不足
2. 34 次 read_file 说明 Agent 在文件读取上效率不高
3. 8 条 Hook 警告说明 Agent 在 PII 安全意识上仍需外部约束
