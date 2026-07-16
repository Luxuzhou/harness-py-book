# Harness-py Book Project

## 项目概述

《HarnessEngineering实战：构建可靠的生产级AIAgent》配套代码仓库。
教学层 `harness_py/`（Ch3-Ch7 构建），生产层 `harness_py_pro/`（Ch8-Ch11 使用），三套新版案例分别对应 Ch8-Ch10 的实战。

## 案例地图

| 章节 | 案例目录 | 语言 | 运行入口 | 验证入口 |
|---|---|---|---|---|
| Ch8 | `cases/refactor_enterprise/` | Java (Spring Boot)，72 文件 / 7,929 行 | `run.py` | `verify.py` |
| Ch9 | `cases/data_compliance/` | Python (FastAPI)，~15,000 行 + 104 tests | `run.py` | `verify.py` |
| Ch10 | `cases/multiagent_enterprise/` | 编排骨架 + cwd 指向 Ch8/Ch9 真实代码 | `run.py` | `verify.py` |

旧版案例（`cases/refactor/`, `cases/medical/`, `cases/fullstack/`）已归档到 `cases/_archive/*_legacy/`。

## 执行策略

1. 先规划再动手：列出所有需要修改的位置，确认后再编辑
2. 用 grep 定位，不要逐段 read
3. 改完必须验证：`python -m pytest tests/ -q`（根测试套件），必要时 `cd cases/data_compliance/target_service && python -m pytest tests/ -q`（案例测试）
4. 如果 bash 输出乱码，改用 read_file 直接检查代码

## Compact Instructions

压缩时保留：当前修改的文件列表、pytest 结果、下一步计划
