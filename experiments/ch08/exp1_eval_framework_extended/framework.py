"""
跨层 Eval 通用框架
====================
把 Ch4 工具描述 eval 抽象为可复用的 Subject / Task / Runner 三件套。

设计原则：
  - Subject 是被测对象，唯一的接口是 apply()/revert()，对 Agent 配置做局部改写
  - Task 是 Golden Set 的一条，描述用户输入 + 期望/禁止信号
  - Runner 跑 (Subject, Task, Seed)，捕获 Agent 的工具调用与输出，与期望比对

复用 Ch4 的 CaptureOnlyTool 思想：只读工具真跑、写入工具假成功，避免
副作用与不必要的 API 成本。
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from harness_py_pro import run as engine_run
from harness_py_pro import ModelConfig, AgentConfig
from harness_py_pro.tools import (
    BaseTool, ToolRegistry, create_default_registry,
)
import harness_py_pro.prompt as _prompt_mod


# 安全上限：单次任务最多捕获多少次工具调用（防 Agent 跑飞）
MAX_CAPTURES_PER_TASK = 5
# Eval Runner 用的临时 sandbox 目录（避免污染调用方 cwd）
_EVAL_SANDBOX = Path(__file__).parent / '_runtime_sandbox'
_EVAL_SANDBOX.mkdir(exist_ok=True)


def _write_fixture(path: str, content: str) -> None:
    target = _EVAL_SANDBOX / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')


def prepare_eval_sandbox() -> None:
    """Create a deterministic mini repo for read/glob/grep based eval tasks."""
    _write_fixture('src/utils.py', 'def format_date(value):\n    return str(value)\n')
    _write_fixture('src/parser.py', 'def parse(text):\n    return text.strip()\n')
    _write_fixture('config/settings.py', 'DEBUG = True\nPORT = 8000\n')
    _write_fixture('tests/test_api.py', 'def test_health():\n    assert True\n')
    _write_fixture(
        'user_service.py',
        'def deprecated_login():\n    pass\n\n'
        'def get_user(user_id):\n    return {"id": user_id}\n',
    )
    _write_fixture('README.md', '# Demo Service\n\nTODO: document deployment.\n')
    _write_fixture('service.yaml', 'model: deepseek\n')
    _write_fixture('deploy/app.yaml', 'provider: deepseek\n')
    _write_fixture('package.json', '{"scripts": {"test": "node test.js"}}\n')
    _write_fixture('pkg/__init__.py', '')
    _write_fixture('app/__init__.py', '')


@dataclass
class Task:
    """Golden Set 中的一条任务。"""
    id: str
    user_prompt: str
    category: str = ''
    # 正向期望：first_call 应是哪个工具，或最终输出应 contain 什么
    expected_first_call: str | None = None
    expected_calls: list[str] = field(default_factory=list)
    expected_contains: list[str] = field(default_factory=list)
    # 反向期望：绝不应触发的工具，或绝不应出现的输出
    forbidden_calls: list[str] = field(default_factory=list)
    forbidden_contains: list[str] = field(default_factory=list)
    notes: str = ''

    @classmethod
    def from_jsonl(cls, path: Path) -> list['Task']:
        with path.open(encoding='utf-8') as fh:
            return [cls(**json.loads(line)) for line in fh if line.strip()]


@dataclass
class Subject:
    """
    被测对象：apply() 时修改 Agent 配置的某一层，revert() 时还原。

    子类应覆盖 apply()/revert()，例如：
      - tool_description: 替换 ToolRegistry 中的 description
      - system_prompt:    替换 build_system_prompt 函数
      - memory_layout:    替换 .claude/memory 的组织方式
      - skill_registry:   替换 SkillRegistry 的注册集合
    """
    name: str
    version: str
    description: str = ''
    # 子类填充：保存还原所需的状态
    _saved_state: Any = None

    def apply(self) -> None:
        raise NotImplementedError(f"{type(self).__name__}.apply() 未实现")

    def revert(self) -> None:
        raise NotImplementedError(f"{type(self).__name__}.revert() 未实现")

    def configure_agent(self, config: AgentConfig) -> AgentConfig:
        return config

    def __enter__(self):
        self.apply()
        return self

    def __exit__(self, *exc):
        self.revert()


@dataclass
class Observation:
    subject_name: str
    subject_version: str
    task_id: str
    seed: int
    first_call: str | None
    all_calls: list[str]
    final_text: str
    matched_expected_first_call: bool
    matched_expected_calls: bool
    matched_expected_contains: bool
    hit_forbidden_calls: bool
    hit_forbidden_contains: bool
    wall_seconds: float
    error: str | None = None


def score(obs: Observation) -> dict[str, int]:
    """把 Observation 转为可聚合的 0/1 指标。"""
    first_ok = int(obs.matched_expected_first_call)
    expected_calls_ok = int(obs.matched_expected_calls)
    contains_ok = int(obs.matched_expected_contains)
    forbidden_call_hit = int(obs.hit_forbidden_calls)
    forbidden_contains_hit = int(obs.hit_forbidden_contains)
    return {
        'first_call_ok': first_ok,
        'expected_calls_ok': expected_calls_ok,
        'contains_ok': contains_ok,
        'forbidden_call_hit': forbidden_call_hit,
        'forbidden_contains_hit': forbidden_contains_hit,
        'policy_ok': int(
            first_ok
            and expected_calls_ok
            and contains_ok
            and not forbidden_call_hit
            and not forbidden_contains_hit
        ),
    }


# -------------------- CaptureOnlyTool --------------------
# 教学说明：这是从 Ch4 eval_runner.py 抽出来的核心模式。每个工具都被
# 包成 CaptureOnlyTool，记录调用参数 + 决定要不要真跑。
#
# 为什么不用 pre_tool hook 拦截？因为 hook 拦截会让 Agent 收到 [HOOK拦截]
# 错误信息，触发"假 recovery"（换工具重试），污染指标。直接包工具能让
# Agent 看到"调用成功"，自然推进工作流。

class CaptureOnlyTool(BaseTool):
    """工具包装器：捕获调用，只读工具真跑、写入工具假成功。"""

    def __init__(self, real_tool: BaseTool, captured: list[dict]):
        self.real = real_tool
        self.captured = captured
        # 把 BaseTool 的属性透传出去，让 ToolRegistry 看起来一致
        self.name = real_tool.name
        self.read_only = getattr(real_tool, 'read_only', False)

    def get_schema(self) -> dict:
        return self.real.get_schema()

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if len(self.captured) >= MAX_CAPTURES_PER_TASK:
            return False, '(eval) max captures per task reached'
        self.captured.append({'name': self.name, 'args': dict(args)})

        if self.read_only:
            try:
                return self.real.execute(args, config)
            except Exception as e:
                # 只读工具也可能失败（路径不存在等），让 Agent 看到真错误
                return False, f'(real) {type(e).__name__}: {e}'

        # 写入/执行类：返回假成功，不产生副作用
        if self.name == 'write_file':
            return True, f"(simulated) Created {args.get('path', '<?>')}."
        if self.name == 'edit_file':
            return True, f"(simulated) Applied edit to {args.get('path', '<?>')}."
        if self.name == 'bash':
            cmd = (args.get('command', '') or '')[:80]
            return True, f"(simulated) Command executed: {cmd}"
        return True, '(simulated) ok'


def _build_capture_registry(captured: list[dict]) -> ToolRegistry:
    """构造一个所有工具都被 CaptureOnlyTool 包装的 registry。"""
    real_registry = create_default_registry()
    wrapped = ToolRegistry()
    for tool in real_registry.list_tools():
        wrapped.register(CaptureOnlyTool(tool, captured))
    return wrapped


# -------------------- CLAUDE.md 隔离 --------------------
# 教学说明：默认情况下 harness_py_pro.prompt.discover_claude_md() 会从 cwd
# 向上递归找 CLAUDE.md 注入到 system prompt。在 eval 场景下，这会把仓库
# 根的 CLAUDE.md 拉进来污染对照。这里用 monkey-patch 把它改成"只查
# cwd 自身，不向上遍历"。
#
# 注意：副作用是全局的。框架退出时不主动还原，因为 eval 进程通常一次性运行。

_ORIG_DISCOVER = _prompt_mod.discover_claude_md


def _isolated_discover(cwd):
    cwd_p = Path(cwd) if not isinstance(cwd, Path) else cwd
    candidate = cwd_p.resolve() / 'CLAUDE.md'
    if candidate.exists():
        try:
            return [('CLAUDE.md', candidate.read_text(encoding='utf-8'))]
        except OSError:
            return []
    return []


_prompt_mod.discover_claude_md = _isolated_discover


class Runner:
    """
    通用评测 Runner。

    工作流：
      with subject:                # apply 改写
        for task in tasks:
          for seed in seeds:
            obs = run_one(task, seed)
            yield obs

    具体的"跑一次 Agent 并捕获工具调用"由 _run_capture_only() 完成，
    实现复用 CaptureOnlyTool。
    """

    def __init__(self, model: str = 'deepseek-chat', temperature: float = 0.0,
                 max_iter: int = 5):
        self.model = model
        self.temperature = temperature
        self.max_iter = max_iter

    def _build_model_config(self, seed: int) -> ModelConfig:
        return ModelConfig(
            model=self.model,
            api_key=os.environ.get('DEEPSEEK_API_KEY', ''),
            base_url=os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1'),
            context_window=64000,
            temperature=self.temperature,
            seed=seed,
        )

    def _build_agent_config(self, subject: Subject | None = None) -> AgentConfig:
        config = AgentConfig(
            cwd=_EVAL_SANDBOX,
            max_iterations=self.max_iter,
            planning_turns=0,
            allow_write=True,
            allow_shell=True,
            sandbox_mode='bypass',
            network_isolated=True,
        )
        if subject is not None:
            config = subject.configure_agent(config)
        return config

    def _run_capture_only(
        self,
        task: Task,
        seed: int,
        subject: Subject | None = None,
    ) -> tuple[list[str], str, str | None]:
        """跑一次 Agent，返回 (all_call_names, final_text, error)。

        all_call_names 是按时序排列的工具名列表，便于 first_call 判断
        和 forbidden_calls 检查。
        """
        captured: list[dict] = []
        registry = _build_capture_registry(captured)
        err = None
        final_text = ''

        try:
            prepare_eval_sandbox()
            result = engine_run(
                task=task.user_prompt,
                model_config=self._build_model_config(seed),
                agent_config=self._build_agent_config(subject),
                tool_registry=registry,
                verbose=False,
            )
            final_text = result.output or ''
        except Exception as e:
            err = f"{type(e).__name__}: {e}"

        all_call_names = [c['name'] for c in captured]
        return all_call_names, final_text, err

    def run(self, subject: Subject, tasks: Iterable[Task],
            seeds: list[int]) -> Iterable[Observation]:
        with subject:
            for task in tasks:
                for seed in seeds:
                    t0 = time.time()
                    err = None
                    all_calls: list[str] = []
                    final_text = ''
                    try:
                        all_calls, final_text, err = self._run_capture_only(task, seed, subject)
                    except Exception as e:
                        err = f"{type(e).__name__}: {e}"
                    first = all_calls[0] if all_calls else None
                    yield Observation(
                        subject_name=subject.name,
                        subject_version=subject.version,
                        task_id=task.id,
                        seed=seed,
                        first_call=first,
                        all_calls=all_calls,
                        final_text=final_text,
                        matched_expected_first_call=(
                            task.expected_first_call is not None and
                            first == task.expected_first_call
                        ),
                        matched_expected_calls=all(
                            c in all_calls for c in task.expected_calls
                        ) if task.expected_calls else True,
                        matched_expected_contains=all(
                            s in final_text for s in task.expected_contains
                        ) if task.expected_contains else True,
                        hit_forbidden_calls=any(
                            c in all_calls for c in task.forbidden_calls
                        ),
                        hit_forbidden_contains=any(
                            s in final_text for s in task.forbidden_contains
                        ),
                        wall_seconds=round(time.time() - t0, 2),
                        error=err,
                    )
