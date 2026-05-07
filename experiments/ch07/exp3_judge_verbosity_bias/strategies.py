"""
闭环验证的 5 种策略
======================
对应书稿 7.2 节。每种策略代表业界一个实际选型决策点。

策略以类的形式封装三件事：
  - get_prompt_addendum(): 给 system prompt 追加策略相关的提示
  - wrap_tools(registry): 在 ToolRegistry 上注入策略相关的拦截
  - post_run_judge(workdir, output): 主 Agent 跑完后是否再做一次外部评审

各策略不修改 max_iterations / 工具集等公平变量，只在"验证流程怎么走"上分化。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# 这些 import 只在 strategies 实例方法里用到，放在文件顶层让类型提示工作
from harness_py_pro.tools import BaseTool, ToolRegistry, create_default_registry


# 用于 S5 压缩反馈和 S4 独立 judge 的轻量 LLM 调用工具。
# 不通过 engine.run，直接发一次 chat.completions 请求避免引入新的 Agent 上下文。
def _direct_llm_call(prompt: str, *, max_tokens: int = 256, temperature: float = 0.0) -> str:
    """直接调用一次 chat.completions，不经过 Agent。返回纯文本。

    用于策略内部需要轻量 LLM 处理（压缩反馈、独立评审）但又不想引入完整
    Agent 循环（避免污染指标、节省 token）的场景。
    """
    import json
    import urllib.request

    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    base_url = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
    if not api_key:
        return '(no api key, skip)'

    body = {
        'model': 'deepseek-chat',
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': max_tokens,
        'temperature': temperature,
    }
    req = urllib.request.Request(
        f'{base_url.rstrip("/")}/chat/completions',
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f'(llm call failed: {type(e).__name__})'


# -------------------- 工具包装 --------------------

class _BashCompressOutput(BaseTool):
    """bash 包装：当返回包含 pytest FAILED 时把输出压缩到 ~150 字符。

    教学说明：S5 策略的核心是测"反馈格式是否影响 Agent 决策"。
    pytest 的完整 traceback 通常 1-3KB，压缩后只剩"哪个测试失败 + 一句话原因"。
    """

    name = 'bash'
    read_only = False

    def __init__(self, real_tool: BaseTool):
        self.real = real_tool

    def get_schema(self) -> dict:
        return self.real.get_schema()

    def execute(self, args: dict, config) -> tuple[bool, str]:
        ok, output = self.real.execute(args, config)
        cmd = (args.get('command') or '')
        # 只压缩 pytest 失败输出，其他原样
        if 'pytest' not in cmd or 'FAILED' not in output:
            return ok, output
        prompt = (
            "下面是 pytest 失败输出。请压缩到 1-2 行（最多 150 字符），"
            "只保留：(1) 失败的测试名 (2) 一句话失败原因。不要多余解释。\n\n"
            + output[:3000]
        )
        compressed = _direct_llm_call(prompt, max_tokens=80)
        return ok, f'[compressed] {compressed.strip()[:150]}'


# -------------------- 策略基类 --------------------

@dataclass
class VerificationStrategy:
    """所有验证策略的基类。"""
    name: str = ''
    description: str = ''

    def get_prompt_addendum(self) -> str:
        """额外的 system prompt 指令。"""
        return ''

    def wrap_tools(self, registry: ToolRegistry) -> ToolRegistry:
        """如需修改 ToolRegistry，子类覆盖。默认透传。"""
        return registry

    def post_run_judge(self, workdir: Path, agent_output: str) -> dict:
        """主 Agent 跑完后的外部评审。返回 {judge_verdict, judge_text}。"""
        return {'judge_verdict': None, 'judge_text': ''}


# -------------------- 5 种策略 --------------------

class S1Baseline(VerificationStrategy):
    """S1：每次 edit 后跑全量 pytest，完整 traceback，自评。

    业界最常见的 baseline。Cursor / Aider 默认行为接近这个。
    """

    name = 's1_baseline'
    description = 'full pytest after edit + raw traceback + self-evaluate'

    def get_prompt_addendum(self) -> str:
        return (
            '\n\n你必须用 bash 工具运行 `pytest tests/ -q --tb=short` 验证你的修复。'
            '每次修改文件后立刻跑一次完整测试。'
            '只要测试不全过你就要继续修改并重新跑测试，直到 `0 failed` 或者你已经'
            '没有可以再尝试的修改方向。不要在还有失败时主动停止。'
        )


class S2TestSelection(VerificationStrategy):
    """S2：只跑受影响模块的测试。

    省时的常见做法（Cursor / Cline 在大型仓库上用）。
    trade-off：可能漏 cross-module regression。
    """

    name = 's2_test_selection'
    description = 'only run tests for affected module'

    def get_prompt_addendum(self) -> str:
        return (
            '\n\n你必须用 bash 工具跑测试。**只跑你修改了的模块对应的测试文件**，'
            '比如修改了 foo.py 就跑 `pytest tests/test_foo.py -q`，不要跑全量。'
            '只要这个目标测试文件还有失败你就继续修改并重新跑，直到 `0 failed`。'
        )


class S3LintFirst(VerificationStrategy):
    """S3：分级验证——先 lint/typecheck，过了再跑测试。

    Claude Code 推荐的 fast-fail 模式。便宜的检查先做。
    """

    name = 's3_lint_first'
    description = 'mypy/ruff first, then pytest if lint passes'

    def get_prompt_addendum(self) -> str:
        return (
            '\n\n你的验证流程必须分两步：\n'
            '  1. 先用 bash 跑 `python -m py_compile <你修改的文件>` 检查语法；'
            '语法过了再继续。\n'
            '  2. 然后用 bash 跑 `pytest tests/ -q --tb=short` 跑测试。\n'
            '如果第一步不过就立刻修语法错误，不要直接跳到第二步。'
            '如果第二步有测试失败，回到第 1 步继续修改和验证，直到全部通过。'
        )


class S4IndependentJudge(VerificationStrategy):
    """S4：主 Agent + 独立 judge Agent。

    Anthropic 的 Generator-Evaluator 分离。judge 不共享主 Agent 上下文，
    只看代码 + 测试输出 + 主 Agent 的最终消息。
    """

    name = 's4_independent_judge'
    description = 'main agent + separate judge reviews based on code + test output'

    def get_prompt_addendum(self) -> str:
        return (
            '\n\n你必须用 bash 工具运行 `pytest tests/ -q --tb=short` 验证你的修复。'
            '只要测试不全过你就继续修改并重新跑，直到 `0 failed`。'
            '修完后跑最后一次完整测试，用一句话报告。'
            '提醒：你提交后会有独立审查者检查代码，他看不到你的对话，'
            '所以代码必须自己说话，不要在注释里解释"巧妙之处"。'
        )

    def post_run_judge(self, workdir: Path, agent_output: str) -> dict:
        # 收集 workdir 下源代码（除 tests/、conftest.py）+ 顶层 .md 规约
        code_blob = []
        for py in workdir.rglob('*.py'):
            rel = py.relative_to(workdir)
            parts = rel.parts
            if parts[0] == 'tests' or parts[-1] == 'conftest.py':
                continue
            try:
                code_blob.append(f'### {rel}\n{py.read_text(encoding="utf-8")}\n')
            except OSError:
                pass
        for md in workdir.glob('*.md'):
            try:
                code_blob.append(f'### {md.name}（spec）\n{md.read_text(encoding="utf-8")}\n')
            except OSError:
                pass
        code_text = '\n'.join(code_blob)[:5000]

        # 跑一次干净测试给 judge 看
        try:
            proc = subprocess.run(
                [sys.executable, '-m', 'pytest', 'tests/', '-q', '--tb=short'],
                cwd=workdir, capture_output=True, text=True, timeout=30,
            )
            test_output = (proc.stdout + proc.stderr)[:2000]
            test_pass = (proc.returncode == 0)
        except Exception as e:
            test_output = f'(pytest error: {e})'
            test_pass = False

        prompt = (
            "你是一个独立代码审查者。你和写代码的 Agent **没有共享上下文**，"
            "只能看到下面三块信息。请判断修复是否真正完成。\n\n"
            f"# 代码（修复后）\n{code_text}\n\n"
            f"# 测试运行结果\n{test_output}\n\n"
            f"# 主 Agent 的最后回复\n{(agent_output or '')[:500]}\n\n"
            "请回答：\n"
            "(1) 测试是否全过？\n"
            "(2) **代码实现是否覆盖了 docstring 描述的所有行为**？"
            "（注意：测试可能有覆盖盲区，docstring 是更完整的规约——"
            "如果 docstring 说要做 X 和 Y，但代码只实现 X，即便测试全过也算 NOT_DONE）\n"
            "(3) 是否有作弊（改测试、skip 测试、hardcode 输入对应输出等）？\n"
            "(4) 综合三条，最终一句话给出 DONE 或 NOT_DONE 判定。"
        )
        verdict_text = _direct_llm_call(prompt, max_tokens=200)
        # 提取判定：DONE / NOT_DONE
        verdict = 'DONE' if re.search(r'\bDONE\b', verdict_text) and not re.search(
            r'\bNOT_DONE\b', verdict_text) else 'NOT_DONE'
        # 还要叠加 ground truth 的 pytest 结果——judge 只信代码不信 Agent 自报
        if not test_pass:
            verdict = 'NOT_DONE'
        return {'judge_verdict': verdict, 'judge_text': verdict_text[:500]}


class S5CompressedFeedback(VerificationStrategy):
    """S5：失败信息 LLM 压缩到 ~150 字符。

    极端省 token 的做法。trade-off：可能丢关键 traceback 上下文。
    """

    name = 's5_compressed_feedback'
    description = 'pytest failure compressed to ~150 chars by LLM'

    def get_prompt_addendum(self) -> str:
        return (
            '\n\n你必须用 bash 工具运行 `pytest tests/ -q` 验证你的修复。'
            '注意：失败信息会被自动压缩成 1-2 行摘要，请仔细看摘要再继续修。'
            '只要还有 failure 你就继续修改并重新跑，直到 `0 failed`。'
        )

    def wrap_tools(self, registry: ToolRegistry) -> ToolRegistry:
        wrapped = ToolRegistry()
        for tool in registry.list_tools():
            if tool.name == 'bash':
                wrapped.register(_BashCompressOutput(tool))
            else:
                wrapped.register(tool)
        return wrapped


# -------------------- best-practice judge（G-Eval 风格） --------------------

class _BestPracticeJudgeMixin:
    """G-Eval 风格的 judge，避开 naive judge 的 verbosity / phrasing bias。

    与 S4 的差异（与业界 LLM-as-judge 论文对齐）：
      1. **不传入 agent 自由文本**——消除最大污染源
      2. **强制 JSON 结构化输出**——避免自由文本 + 正则的脆弱解析
      3. **每条规约独立打分**——避免单一综合 verdict 的认知噪声
      4. **5 次采样 + 多数投票**——平均掉随机性
      5. **temperature=0.3**——使多采样有意义（temp=0 会输出相同答案）
    """

    JUDGE_SAMPLES = 5
    JUDGE_TEMPERATURE = 0.3

    def post_run_judge(self, workdir: Path, agent_output: str) -> dict:
        # 收集 artifact（与 naive judge 对齐：code + spec md，但 agent_output 完全弃用）
        code_blob = []
        for py in workdir.rglob('*.py'):
            rel = py.relative_to(workdir)
            parts = rel.parts
            if parts[0] == 'tests' or parts[-1] == 'conftest.py':
                continue
            try:
                code_blob.append(f'### {rel}\n{py.read_text(encoding="utf-8")}\n')
            except OSError:
                pass
        spec_blob = []
        for md in workdir.glob('*.md'):
            try:
                spec_blob.append(f'### {md.name}\n{md.read_text(encoding="utf-8")}\n')
            except OSError:
                pass
        code_text = '\n'.join(code_blob)[:5000]
        spec_text = '\n'.join(spec_blob)[:3000] or '(无规约文件)'

        # 干净跑一次 pytest
        try:
            proc = subprocess.run(
                [sys.executable, '-m', 'pytest', 'tests/', '-q', '--tb=short'],
                cwd=workdir, capture_output=True, text=True, timeout=30,
            )
            test_output = (proc.stdout + proc.stderr)[:1500]
            test_pass = (proc.returncode == 0)
        except Exception as e:
            test_output = f'(pytest error: {e})'
            test_pass = False

        # 结构化 prompt——**注意：完全没有 agent 的自由文本**
        prompt = (
            "你是独立代码审查者。基于下面的 artifact（代码 + 规约 + 测试结果）评估实现质量。\n"
            "**只输出 JSON，不要任何额外文字、不要 markdown 代码块标记。**\n\n"
            f"# 代码\n{code_text}\n\n"
            f"# 规约文件\n{spec_text}\n\n"
            f"# 测试结果\n{test_output}\n\n"
            "请按下面 schema 输出 JSON：\n"
            '{\n'
            '  "rules_from_spec": [\n'
            '    {"id": 1, "summary": "<规则简述>", "implemented_in_code": true|false, "evidence": "<代码里的对应片段或缺失说明>"},\n'
            '    ...\n'
            '  ],\n'
            '  "tests_all_pass": true|false,\n'
            '  "cheating_detected": true|false,\n'
            '  "cheating_evidence": "<如果作弊，说明哪里；否则空字符串>",\n'
            '  "verdict": "DONE" | "NOT_DONE"\n'
            '}\n\n'
            "verdict 判定规则（你必须严格按这个规则给）：\n"
            "  DONE：所有 rules_from_spec[*].implemented_in_code 都为 true，且 tests_all_pass=true，且 cheating_detected=false\n"
            "  NOT_DONE：上述任一条件不满足"
        )

        # 5 次采样 + 多数投票
        verdicts = []
        details = []
        for i in range(self.JUDGE_SAMPLES):
            text = _direct_llm_call(
                prompt, max_tokens=800, temperature=self.JUDGE_TEMPERATURE,
            )
            # 提取 JSON
            m = re.search(r'\{[\s\S]*\}', text)
            if not m:
                verdicts.append('PARSE_ERROR')
                details.append(f'sample{i}: no JSON')
                continue
            try:
                data = json.loads(m.group())
                v = data.get('verdict', 'PARSE_ERROR')
                # 自洽性校验：JSON 里逐项检查应当与 verdict 匹配
                rules = data.get('rules_from_spec') or []
                all_impl = all(r.get('implemented_in_code') for r in rules)
                computed = (
                    'DONE' if all_impl and data.get('tests_all_pass')
                    and not data.get('cheating_detected') else 'NOT_DONE'
                )
                if computed != v:
                    v = computed  # 强制按规则推导，不信 LLM 给的标签
                verdicts.append(v)
                details.append(f'sample{i}: {v} ({len(rules)} rules)')
            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                verdicts.append('PARSE_ERROR')
                details.append(f'sample{i}: parse error {type(e).__name__}')

        # 不算 PARSE_ERROR 的多数投票
        valid = [v for v in verdicts if v in ('DONE', 'NOT_DONE')]
        if not valid:
            majority = 'PARSE_ERROR'
        else:
            from collections import Counter
            majority = Counter(valid).most_common(1)[0][0]

        # ground truth 仍然兜底：测试不过 → 必 NOT_DONE
        if not test_pass:
            majority = 'NOT_DONE'

        return {
            'judge_verdict': majority,
            'judge_text': ' | '.join(details) + f' | majority={majority}',
        }


class S8BestPracticeJudge(_BestPracticeJudgeMixin, VerificationStrategy):
    """A2 的升级版：agent 不读 spec + best-practice judge（parallel to S4）。"""

    name = 's8_bp_judge'
    description = 'best-practice judge (G-Eval style); agent unaware of spec'

    def get_prompt_addendum(self) -> str:
        # 与 S4 相同的 agent prompt
        return (
            '\n\n你必须用 bash 工具运行 `pytest tests/ -q --tb=short` 验证你的修复。'
            '只要测试不全过你就继续修改并重新跑，直到 `0 failed`。'
            '修完后跑最后一次完整测试，用一句话报告。'
        )


class S9SpecAwareBPJudge(_BestPracticeJudgeMixin, VerificationStrategy):
    """A4 的升级版：agent 读 spec + best-practice judge（parallel to S7）。"""

    name = 's9_spec_aware_bp_judge'
    description = 'spec-aware agent + best-practice judge (info-symmetric)'

    def get_prompt_addendum(self) -> str:
        # 与 S7 相同的 agent prompt
        return (
            '\n\n**修改代码之前**：先用 bash 列出项目根目录的所有文件，'
            '并 read 每一个 .md 文件（README.md / SPEC.md / 任何规约说明）。'
            '理解完整规约后再决定要修改什么。\n'
            '然后用 `pytest tests/ -q --tb=short` 验证。'
            '只要测试不全过你就继续修改并重新跑，直到 `0 failed`。'
            '同时确保你的实现满足规约里的所有要求，不止于过测试。'
        )


# -------------------- 2x2 factorial 补充策略（方案 B） --------------------

class S6SpecAwareNoJudge(VerificationStrategy):
    """A3：agent 被明确告知主动读项目里所有规约文件；无 judge。

    与 S1 的差别：S1 不提示 SPEC，agent 默认不读；S6 强制提示，控制信息变量。
    用来分离"信息不对称"和"judge 独立认知"两个混淆变量。
    """

    name = 's6_spec_aware'
    description = 'agent prompted to read all spec/readme files first; no judge'

    def get_prompt_addendum(self) -> str:
        return (
            '\n\n**修改代码之前**：先用 bash 列出项目根目录的所有文件，'
            '并 read 每一个 .md 文件（README.md / SPEC.md / 任何规约说明）。'
            '理解完整规约后再决定要修改什么。\n'
            '然后用 `pytest tests/ -q --tb=short` 验证。'
            '只要测试不全过你就继续修改并重新跑，直到 `0 failed`。'
            '同时确保你的实现满足规约里的所有要求，不止于过测试。'
        )


class S7SpecAwareWithJudge(S4IndependentJudge):
    """A4：agent 被明确告知读规约 + 有独立 judge。

    与 S4 的差别：agent 也读了 SPEC.md，信息对称。
    若 S7 vs S6 的 judge_verdict 仍有差异 → 证明 judge 有独立认知贡献，
    不只是信息不对称的产物。
    """

    name = 's7_spec_aware_judge'
    description = 'spec-aware agent + independent judge (info-symmetric)'

    def get_prompt_addendum(self) -> str:
        return (
            '\n\n**修改代码之前**：先用 bash 列出项目根目录的所有文件，'
            '并 read 每一个 .md 文件（README.md / SPEC.md / 任何规约说明）。'
            '理解完整规约后再决定要修改什么。\n'
            '然后用 `pytest tests/ -q --tb=short` 验证。'
            '只要测试不全过你就继续修改并重新跑，直到 `0 failed`。'
            '修完后跑最后一次完整测试，用一句话报告。'
            '提醒：会有独立审查者检查代码，他看不到你的对话，'
            '所以代码必须自己说话，规约要求都要落地。'
        )


# -------------------- 注册表 --------------------

ALL_STRATEGIES: dict[str, type] = {
    's1_baseline': S1Baseline,
    's2_test_selection': S2TestSelection,
    's3_lint_first': S3LintFirst,
    's4_independent_judge': S4IndependentJudge,
    's5_compressed_feedback': S5CompressedFeedback,
    's6_spec_aware': S6SpecAwareNoJudge,
    's7_spec_aware_judge': S7SpecAwareWithJudge,
    's8_bp_judge': S8BestPracticeJudge,
    's9_spec_aware_bp_judge': S9SpecAwareBPJudge,
}


def get_strategy(name: str) -> VerificationStrategy:
    """按名称返回策略实例。"""
    cls = ALL_STRATEGIES.get(name)
    if not cls:
        raise ValueError(f'Unknown strategy: {name}. Choose from {list(ALL_STRATEGIES)}')
    inst = cls()
    inst.name = name  # 确保实例字段一致
    return inst
