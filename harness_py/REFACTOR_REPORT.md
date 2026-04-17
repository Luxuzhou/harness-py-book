# Harness-py 重构报告

> 生成时间: 2026-04-08
> 分析目标: `harness_py/` 目录下全部 11 个 Python 文件
> 总代码行数: 1,473 行

---

## 一、项目结构概览

```
harness_py/                   # 《驾驭AI》配套 Agent 框架
│
├── __init__.py          (  12 行)  包声明 + 版本号
├── agent.py             ( 245 行)  核心 Agent 循环（run / resume）
├── config.py            (  61 行)  ModelConfig + AgentConfig 数据类
├── http_client.py       ( 127 行)  HTTP 客户端（requests + 重试 + jitter）
├── tools.py             ( 355 行)  6 个工具实现 + Schema 定义 + 注册表
├── compressor.py        ( 180 行)  四级上下文压缩器
├── token_budget.py      (  55 行)  Token 预算五区分配
├── prompt.py            ( 125 行)  System Prompt 组装 + 安全扫描
├── memory.py            ( 122 行)  记忆管理 + Dream 整理
├── loop_guard.py        (  71 行)  循环守卫（死循环检测）
└── session.py           ( 119 行)  Session 持久化（JSONL）
```

### 架构分层

| 层级 | 模块 | 职责 |
|------|------|------|
| 约束层 | `config.py` | 模型参数、权限、规划阶段配置 |
| 工具层 | `tools.py` | 6 个工具（read/write/edit/grep/glob/bash） |
| 上下文层 | `prompt.py`, `token_budget.py` | Prompt 构建、预算管理 |
| 记忆层 | `memory.py`, `session.py`, `compressor.py` | 持久化记忆、上下文压缩 |
| 验证层 | `loop_guard.py` | 死循环检测、异常干预 |
| 编排层 | `agent.py` | 核心循环、各层汇聚 |
| 基础设施 | `http_client.py` | API 通信 |

### 各文件行数统计

| 文件 | 行数 | 主要功能 |
|------|------|----------|
| `__init__.py` | 12 | 包声明，定义 `__version__ = '0.1.0'` |
| `agent.py` | 245 | `run()` 执行任务主循环，`resume()` 断点续接，`RunResult` 结果数据类 |
| `config.py` | 61 | `ModelConfig`（模型/API配置，支持环境变量），`AgentConfig`（运行参数），`ensure_utf8_console()` |
| `http_client.py` | 127 | `LLMClient` 封装 OpenAI 兼容 API，内置连接池、5 次重试、去相关 jitter、Session 重建 |
| `tools.py` | 355 | 6 个工具的 JSON Schema + 实现（read_file/write_file/edit_file/grep/glob/bash），分阶段工具解锁 |
| `compressor.py` | 180 | `Compressor` 四级压缩（Microcompact→Snipping→Compaction→Reactive），孤立工具对修复 |
| `token_budget.py` | 55 | `TokenBudget` 五区分配，`estimate_tokens()` 中英文估算，`should_compress()` 阈值判断 |
| `prompt.py` | 125 | `build_system_prompt()` 组装系统提示，`discover_claude_md()` 发现上下文文件，`scan_context_threats()` 安全扫描 |
| `memory.py` | 122 | `load_memory_bundle()` 加载记忆，`write_memory()` 写入，`dream()` 四阶段整理（去重/日期修正/清理） |
| `loop_guard.py` | 71 | `LoopGuard` 检测重复调用、连续失败、频率异常，触发干预消息 |
| `session.py` | 119 | `SessionWriter` JSONL 追加写入，`load_session_messages()` 事件重放，`list_sessions()` 列出会话 |

---

## 二、发现的问题清单（按严重程度排序）

### 🔴 高优先级（应立即修复）

#### H1. HTTP Session 重建时 Retry 配置不一致 — `http_client.py`

**类型**: Bug
**位置**: `__init__()` (L46-54) vs `_rebuild_session()` (L116-119)

初始创建 Session 时配置了 `Retry(total=5, connect=3, read=3, ...)`，但 `_rebuild_session()` 中遗漏了 `connect=3` 和 `read=3` 参数：

```python
# __init__ 中 (完整)
retry = Retry(total=5, connect=3, read=3, backoff_factor=0.5, ...)

# _rebuild_session 中 (缺少 connect/read)
Retry(total=5, backoff_factor=0.5, ...)
```

**影响**: Session 重建后，连接重试次数从 3 降到 urllib3 默认值（0），导致网络抖动时更容易失败。这是一个 copy-paste 引入的 bug。

#### H2. HTTP Session 创建逻辑重复 — `http_client.py`

**类型**: 代码重复
**位置**: `__init__()` (L44-62) 和 `_rebuild_session()` (L110-127)

两处代码几乎完全相同（创建 Retry → HTTPAdapter → Session → mount → headers），但参数还不一致（见 H1）。

**建议**: 提取 `_create_session()` 方法，两处统一调用。

#### H3. `agent.py` 有 3 个未使用的 import

**类型**: 代码卫生
**位置**: agent.py L13-17, L22

| Import | 状态 |
|--------|------|
| `import sys` | ❌ 未使用 — agent.py 中无 `sys.*` 引用 |
| `import time` | ❌ 未使用 — agent.py 中无 `time.*` 调用 |
| `from .tools import TOOL_REGISTRY` | ❌ 未使用 — 仅用了 `TOOL_SCHEMAS`、`execute_tool`、`get_schemas_for_phase` |

---

### 🟡 中优先级（建议修复）

#### M1. `http_client.py` 未使用的 `Iterator` import

**位置**: L12 `from typing import Any, Iterator`
**说明**: `Iterator` 从未在文件中引用，疑似移除流式实现时遗留。

#### M2. `tools.py` 未使用的 import + 函数体内 import

| 问题 | 位置 |
|------|------|
| `import json` 未使用 | L11 — tools.py 中无 `json.*` 调用 |
| `from typing import Any` 未使用 | L20 — 函数签名中未使用 `Any` |
| `import sys` 在函数体内 | L248（`tool_bash` 内部） — 应移至文件顶部 |

#### M3. `prompt.py` 函数体内 import

**位置**: L118 `import datetime`（在 `build_system_prompt()` 内部）
**说明**: 与项目其他文件的顶部 import 风格不一致，应移至文件顶部。

#### M4. `memory.py` + `session.py` 重复的 Git 子进程调用模式

**位置**:
- `memory.py` L22-24: `subprocess.run(['git', 'rev-parse', '--show-toplevel'], ...)`
- `session.py` L26-27: `subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], ...)`

两处都用相同模式（`capture_output=True, text=True, timeout=5, try/except`）调用 Git。

**建议**: 提取共享工具函数：

```python
# 新建 harness_py/utils.py 或放入 config.py
def git_command(*args: str, cwd: Path | None = None) -> str | None:
    try:
        r = subprocess.run(['git', *args], capture_output=True,
                          text=True, timeout=5, cwd=str(cwd) if cwd else None)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None
```

#### M5. `memory.py` 和 `session.py` 未使用的 `import os`

| 文件 | 位置 |
|------|------|
| `memory.py` | L8 — 所有路径操作都用 `pathlib.Path`，`os` 未被引用 |
| `session.py` | L9 — 同上 |

#### M6. `compressor.py` 未使用的 `field` import

**位置**: L14 `from dataclasses import dataclass, field`
**说明**: `Compressor` 数据类所有字段都用普通默认值，`field` 未被调用。

---

### 🟢 低优先级（建议改进）

#### L1. `agent.py` 中 System Prompt 组装逻辑重复

**位置**: L75-77（初始构建）和 L111-116（压缩后重建）

两处都调用 `build_system_prompt(ac.cwd)` + `load_memory_bundle(ac.cwd)` 并拼接。建议提取辅助函数：

```python
def _build_full_system(cwd: Path) -> str:
    prompt = build_system_prompt(cwd)
    memory = load_memory_bundle(cwd)
    return prompt + ('\n' + memory if memory else '')
```

#### L2. `tools.py` 中路径解析模式重复 5 次

**位置**: L162, L181, L190, L204, L229

`Path(config.cwd) / args['path']` 出现在每个工具函数中。可提取：

```python
def _resolve_path(config: AgentConfig, args: dict) -> Path:
    return Path(config.cwd) / args['path']
```

#### L3. `memory.py` `dream()` 在 glob 迭代时修改目录

**位置**: L75-109
**风险**: `tf.unlink()` 在遍历 `mem_dir.glob('*.md')` 期间调用，某些平台上可能导致迭代器异常。
**修复**: 改为 `for tf in list(mem_dir.glob('*.md')):`

#### L4. `session.py` `list_sessions()` 重复 stat 调用

**位置**: L113-115

```python
# 当前: stat() 被调用两次
for path in sorted(..., key=lambda p: -p.stat().st_mtime):
    mtime = path.stat().st_mtime  # 第二次 stat

# 建议: 缓存 stat 结果
entries = [(p, p.stat()) for p in directory.glob('*.jsonl')]
entries.sort(key=lambda x: -x[1].st_mtime)
```

#### L5. `__init__.py` 缺少公开 API 导出

当前 `__init__.py` 仅定义 `__version__`，无法 `from harness_py import run`。建议添加：

```python
from .agent import run, resume, RunResult
from .config import ModelConfig, AgentConfig
```

#### L6. `uuid4` 使用方式不一致

- `agent.py` L69: `uuid4().hex`（直接调用）
- `session.py` L21: `def _uuid(): return uuid4().hex`（包装函数）

建议统一：要么都用直接调用，要么共享一个工具函数。

#### L7. `loop_guard.py` 使用 MD5 哈希

**位置**: L50 `hashlib.md5(...)`
**说明**: 此处仅用于指纹去重，非安全用途，功能上无问题。但在 FIPS 模式系统上 MD5 可能被禁用，改用 `hashlib.sha256` 更稳妥。

---

## 三、未使用 Import 汇总表

| 文件 | 未使用 Import | 严重程度 |
|------|--------------|----------|
| `agent.py` | `sys` | 中 |
| `agent.py` | `time` | 中 |
| `agent.py` | `TOOL_REGISTRY` (from .tools) | 低 |
| `compressor.py` | `field` (from dataclasses) | 低 |
| `http_client.py` | `Iterator` (from typing) | 中 |
| `tools.py` | `json` | 中 |
| `tools.py` | `Any` (from typing) | 低 |
| `memory.py` | `os` | 低 |
| `session.py` | `os` | 低 |

**函数体内 import**（应移至顶部）:

| 文件 | Import | 位置 |
|------|--------|------|
| `tools.py` | `import sys` | L248 (tool_bash 内) |
| `prompt.py` | `import datetime` | L118 (build_system_prompt 内) |

---

## 四、建议的重构方案

### 第一阶段：修 Bug + 清理 Import（预计 15 分钟）

1. **修复 `http_client.py` Session 重建 bug**
   - 提取 `_create_session()` 方法，统一 Retry 配置
   - 同时消除代码重复

2. **清理全部未使用 import**
   - 逐文件删除上表中的 9 个未使用 import
   - 将 `tools.py:import sys` 和 `prompt.py:import datetime` 移至文件顶部

3. **运行测试验证**: `python -m pytest tests/ -v`

### 第二阶段：消除重复逻辑（预计 20 分钟）

4. **新建 `harness_py/utils.py`**，集中：
   - `git_command()` — 统一 Git 子进程调用（memory.py + session.py 共用）
   - `resolve_tool_path()` — 统一工具路径解析（tools.py 5 处共用）

5. **`agent.py` 提取 `_build_full_system()`** 辅助函数
   - 消除 system prompt 组装的两处重复

6. **运行测试验证**

### 第三阶段：健壮性改进（预计 10 分钟）

7. **`memory.py` dream()** — 将 glob 结果转为 list 再迭代
8. **`session.py` list_sessions()** — 缓存 stat 结果
9. **`__init__.py`** — 添加公开 API 导出
10. **运行测试验证**

### 重构后预期效果

| 指标 | 重构前 | 重构后 |
|------|--------|--------|
| 未使用 import | 9 个 | 0 个 |
| 函数内 import | 2 处 | 0 处 |
| 重复代码块 | 5 处 | 0 处 |
| 已知 Bug | 1 个 (Retry 配置) | 0 个 |
| 文件数 | 11 | 12 (+utils.py) |

---

## 附录：每个文件的 Import 清单

<details>
<summary>点击展开完整 import 分析</summary>

### agent.py
```python
from __future__ import annotations    # ✅ 使用
import json                           # ✅ 使用 (L176)
import sys                            # ❌ 未使用
import time                           # ❌ 未使用
from pathlib import Path              # ✅ 使用 (隐式, 通过 / 运算符)
from uuid import uuid4                # ✅ 使用 (L69)
from dataclasses import dataclass, field  # ✅ 使用

from .config import ModelConfig, AgentConfig, ensure_utf8_console  # ✅ 全部使用
from .http_client import LLMClient    # ✅ 使用
from .tools import TOOL_SCHEMAS, TOOL_REGISTRY, execute_tool, get_schemas_for_phase
#               ✅             ❌            ✅             ✅
from .compressor import Compressor    # ✅ 使用
from .loop_guard import LoopGuard     # ✅ 使用
from .token_budget import TokenBudget, estimate_tokens, should_compress, format_budget  # ✅ 全部使用
from .prompt import build_system_prompt  # ✅ 使用
from .memory import load_memory_bundle   # ✅ 使用
from .session import SessionWriter       # ✅ 使用
```

### http_client.py
```python
from __future__ import annotations    # ✅
import json                           # ✅ (resp.json 间接, 但实际未直接调用 json.*)
import time                           # ✅ (L34, L90)
import threading                      # ✅ (L23)
from typing import Any, Iterator      # Any ✅, Iterator ❌
import requests                       # ✅
from requests.adapters import HTTPAdapter  # ✅
from urllib3.util.retry import Retry  # ✅
from .config import ModelConfig       # ✅
```

### tools.py
```python
from __future__ import annotations    # ✅
import json                           # ❌ 未使用
import os                             # ✅ (L40)
import re                             # ✅ (L207)
import shutil                         # ✅ (L38, L45-46)
import subprocess                     # ✅ (L261)
import threading                      # ✅ (L285)
import queue                          # ✅ (L268)
import time                           # ✅ (L291)
from pathlib import Path              # ✅
from typing import Any                # ❌ 未使用
from .config import AgentConfig       # ✅
```

</details>
