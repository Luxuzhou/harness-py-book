"""
失败挖掘 → CLAUDE.md 规则候选生成
====================================
对应书稿 8.5。从 session.jsonl 中挖掘高频失败，调用 LLM 生成规则候选。

流程：
  1. 加载 N 份 session.jsonl
  2. 扫描 (tool_call → error_return) 对，按 (tool, error_class) 聚合
  3. 取 Top-K，对每个 pattern 调用 LLM 生成规则候选
  4. 输出 markdown 报告 + csv 失败清单

用法：
    python run.py --smoke                      # 用 sessions_sample/
    python run.py --sessions '~/.harness-py/sessions/*.jsonl'
    python run.py --no-synthesis               # 跳过 LLM 生成步骤
    python run.py --top 20
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from pathlib import Path

# 环境
_REPO_ROOT = Path(__file__).resolve().parents[3]
_env_file = _REPO_ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        if '=' in _line and not _line.strip().startswith('#'):
            k, _, v = _line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

# API key 兼容：OPENAI/HARNESS/DEEPSEEK 任一即可，统一回填到 DEEPSEEK_API_KEY
_resolved_key = (os.environ.get('DEEPSEEK_API_KEY')
                 or os.environ.get('HARNESS_API_KEY')
                 or os.environ.get('OPENAI_API_KEY') or '')
if _resolved_key:
    os.environ.setdefault('DEEPSEEK_API_KEY', _resolved_key)
_resolved_base = (os.environ.get('DEEPSEEK_BASE_URL')
                  or os.environ.get('HARNESS_BASE_URL')
                  or os.environ.get('OPENAI_BASE_URL') or '')
if _resolved_base:
    os.environ.setdefault('DEEPSEEK_BASE_URL', _resolved_base)

sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / 'experiments' / 'ch08'))

from feedback_loop import generate_candidate, mine_failures  # noqa: E402

EXP_DIR = Path(__file__).parent
SAMPLE_DIR = EXP_DIR / 'sessions_sample'
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)


# ============ 失败分类（与 examples/ch08_feedback.py 同步）============
# ============ Session 加载 ============
def load_sessions(paths: list[Path]) -> list[dict]:
    """合并多个 jsonl 为单一 turn 列表，保留 source 字段标记来源。"""
    turns: list[dict] = []
    for p in paths:
        if not p.exists():
            print(f"  跳过不存在: {p}")
            continue
        with p.open(encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    obj['_source'] = p.name
                    turns.append(obj)
                except json.JSONDecodeError:
                    continue
    return turns


# ============ 失败挖掘 ============
def mine(turns: list[dict]) -> list[dict]:
    """
    返回失败模式列表，每条 dict:
      tool, error_class, count, error_samples (≤3), prompt_samples (≤3)
    """
    return mine_failures(turns)


# ============ 规则生成（调 LLM）============
PROMPT_TEMPLATE = """你是 Harness 工程师。下面是 Agent 在过去一周内反复出现的失败模式：

失败次数：{count}
工具：{tool}
错误类别：{error_class}
典型错误：
{error_block}

典型用户请求：
{prompt_block}

请生成一条 CLAUDE.md 规则候选，目标是让 Agent 下次避免这个失败。
规则应该：
1. 具体（指明工具与场景）
2. 可执行（Agent 读到能立刻照做）
3. 短（≤3 句）

输出格式：
## 规则
<rule body>

## 适用场景
<one line>
"""


def call_llm(prompt: str, model: str = 'deepseek-chat') -> str:
    """调用 DeepSeek-V3 生成规则候选。失败时返回 placeholder。"""
    try:
        from harness_py_pro.client import LLMClient
        from harness_py_pro.config import ModelConfig
        client = LLMClient(ModelConfig(
            model=model,
            temperature=0.3,
            api_key=os.environ.get('DEEPSEEK_API_KEY', ''),
            base_url=os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1'),
        ))
        resp = client.complete([{'role': 'user', 'content': prompt}])
        return resp.get('content', '').strip()
    except Exception as e:
        return f"[LLM 调用失败: {type(e).__name__}: {e}]\n## 规则\n（待手动填写）\n## 适用场景\n（待手动填写）"


def synthesize_rule(failure: dict) -> str:
    err_block = '\n'.join(f"  - {e}" for e in failure['error_samples'])
    prompt_block = '\n'.join(f"  - {p}" for p in failure['prompt_samples']) or '  - （无）'
    prompt = PROMPT_TEMPLATE.format(
        count=failure['count'],
        tool=failure['tool'],
        error_class=failure['error_class'],
        error_block=err_block,
        prompt_block=prompt_block,
    )
    return call_llm(prompt)


# ============ 输出 ============
def write_csv(failures: list[dict], path: Path) -> None:
    with path.open('w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['tool', 'error_class', 'count', 'sample_prompts'])
        for f in failures:
            w.writerow([f['tool'], f['error_class'], f['count'],
                        ' | '.join(f['prompt_samples'])])


def write_candidates(failures: list[dict], path: Path) -> None:
    candidates = [generate_candidate(f).to_dict() for f in failures]
    path.write_text(json.dumps(candidates, indent=2, ensure_ascii=False), encoding='utf-8')


def write_report(failures: list[dict], rules: list[str], path: Path) -> None:
    lines = ['# 失败挖掘报告 → CLAUDE.md 规则候选\n']
    lines.append(f"\n共发现 {len(failures)} 个失败 pattern，下面是 Top-{len(rules)}。\n")
    lines.append("\n人工 Review 流程：\n")
    lines.append('- 接受：把 `## 规则` 段贴入 `CLAUDE.md`\n')
    lines.append("- 修改：编辑后接受\n")
    lines.append("- 拒绝：noise，不接入\n\n---\n")
    for i, (f, r) in enumerate(zip(failures, rules), 1):
        lines.append(f"\n## #{i} {f['tool']} / {f['error_class']} （出现 {f['count']} 次）\n\n")
        lines.append("**典型错误**：\n")
        for e in f['error_samples']:
            lines.append(f"- `{e}`\n")
        lines.append("\n**典型用户请求**：\n")
        for p in f['prompt_samples'] or ['（无）']:
            lines.append(f"- {p}\n")
        lines.append("\n**LLM 生成的规则候选**：\n\n")
        lines.append(r)
        lines.append("\n\n---\n")
    path.write_text(''.join(lines), encoding='utf-8')


# ============ 主入口 ============
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--smoke', action='store_true', help='用 sessions_sample/ 跑最小流程')
    ap.add_argument('--sessions', type=str, default=None,
                    help='glob 模式，例：~/.harness-py/sessions/*.jsonl')
    ap.add_argument('--top', type=int, default=10)
    ap.add_argument('--no-synthesis', action='store_true', help='跳过 LLM 生成')
    args = ap.parse_args()

    if args.sessions:
        paths = [Path(os.path.expanduser(p)) for p in glob.glob(os.path.expanduser(args.sessions))]
    else:
        paths = sorted(SAMPLE_DIR.glob('*.jsonl'))
        print(f"未指定 --sessions，使用 sessions_sample/ 下的 {len(paths)} 份样本")

    turns = load_sessions(paths)
    print(f"共加载 {len(turns)} 条 turn")

    failures = mine(turns)
    print(f"识别出 {len(failures)} 个失败 pattern")
    failures = failures[:args.top]
    print(f"取 Top-{len(failures)} 进入规则生成")

    write_csv(failures, RESULTS / 'failures_top.csv')
    write_candidates(failures, RESULTS / 'rule_candidates.json')

    if args.no_synthesis:
        print("跳过 LLM 规则生成 (--no-synthesis)")
        print(f"候选变更已写入: {RESULTS / 'rule_candidates.json'}")
        return

    rules: list[str] = []
    for i, f in enumerate(failures, 1):
        print(f"  [{i}/{len(failures)}] 生成规则: {f['tool']} / {f['error_class']} ...")
        rules.append(synthesize_rule(f))

    write_report(failures, rules, RESULTS / 'rules_candidate.md')
    print(f"\n完成：")
    print(f"  - {RESULTS / 'failures_top.csv'}")
    print(f"  - {RESULTS / 'rules_candidate.md'}")
    print(f"\n下一步：人工 review rules_candidate.md，把接受的部分贴入 CLAUDE.md。")


if __name__ == '__main__':
    main()
