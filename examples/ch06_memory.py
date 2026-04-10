"""
第6章 记忆管理与上下文压缩演示
================================
四级压缩、Token预算、Memory系统、Session持久化。
直接调用harness_py框架模块。

用法: python examples/ch06_memory.py
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, '.')

from harness_py.compressor import Compressor
from harness_py.token_budget import TokenBudget, estimate_tokens, should_compress, format_budget
from harness_py.memory import load_memory_bundle, write_memory, dream
from harness_py.session import SessionWriter, load_session_messages


def demo_compression():
    """四级压缩演示。"""
    print('=== 四级压缩 ===\n')

    comp = Compressor(preserve_messages=2)

    # 构造一个膨胀的对话
    msgs = [{'role': 'system', 'content': 'You are a coding assistant.'}]
    for i in range(15):
        msgs.append({'role': 'user', 'content': f'请读取文件 file_{i}.py'})
        msgs.append({'role': 'tool', 'content': f'def function_{i}():\n    ' + 'x = 1\n    ' * 50})

    before = comp.total_tokens(msgs)
    print(f'压缩前: {len(msgs)} 条消息, ~{before:,} tokens')

    # Level 1: Microcompact
    result = comp._microcompact(msgs, preserve=2)
    after_mc = comp.total_tokens(result)
    truncated = sum(1 for m in result if '[truncated]' in str(m.get('content', '')))
    print(f'Microcompact: ~{after_mc:,} tokens (截断了 {truncated} 条)')

    # Level 2: Snip
    result = comp._snip(msgs, preserve=2)
    after_snip = comp.total_tokens(result)
    print(f'Snip: ~{after_snip:,} tokens ({len(result)} 条消息)')

    # 完整压缩流程
    result = comp.compress(msgs, target_tokens=500)
    after_full = comp.total_tokens(result)
    print(f'完整压缩: ~{after_full:,} tokens (目标500)')
    print(f'压缩率: {(1 - after_full/before)*100:.1f}%')


def demo_token_budget():
    """Token预算五区分配。"""
    print('\n=== Token预算 ===\n')

    budget = TokenBudget.allocate(128_000)
    print(f'128K窗口分配:')
    print(f'  System Prompt:  {budget.system_prompt:,} (10%)')
    print(f'  Memory:         {budget.memory:,} (5%)')
    print(f'  Current Task:   {budget.current_task:,} (20%)')
    print(f'  History:        {budget.history:,} (50%)')
    print(f'  Output Reserve: {budget.output_reserve:,} (15%)')

    # 压缩触发判断
    need, reason = should_compress(budget, 60_000, threshold_pct=0.8)
    print(f'\n60K tokens时压缩? {need} ({reason})')
    need, reason = should_compress(budget, 40_000, threshold_pct=0.8)
    print(f'40K tokens时压缩? {need}')


def demo_memory():
    """Memory系统。"""
    print('\n=== Memory系统 ===\n')

    tmpdir = tempfile.mkdtemp()
    try:
        cwd = Path(tmpdir)

        # 写入记忆
        write_memory(cwd, 'user_role', 'user', '用户是一名后端工程师，熟悉Python和Go。')
        write_memory(cwd, 'project_arch', 'project', '项目使用FastAPI + PostgreSQL，微服务架构。')
        write_memory(cwd, 'feedback_testing', 'feedback', '不要mock数据库，用真实测试数据库。')

        # 加载记忆
        bundle = load_memory_bundle(cwd)
        print(f'Memory bundle: {len(bundle)} 字符')
        for line in bundle.splitlines()[:5]:
            print(f'  {line}')

        # Dream整理
        result = dream(cwd)
        print(f'\nDream结果: {result}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def demo_session():
    """Session持久化。"""
    print('\n=== Session持久化 ===\n')

    tmpdir = tempfile.mkdtemp()
    try:
        session_dir = Path(tmpdir) / 'sessions'
        writer = SessionWriter('test-session-001', session_dir, Path('.'))

        writer.write_message('system', 'You are a coding assistant.')
        writer.write_message('user', '请帮我分析代码')
        writer.write_message('assistant', '好的，让我先读取项目结构。')
        writer.write_event({'type': 'tool_call', 'tool': 'glob_search'})
        writer.write_message('tool', '{"files": ["main.py", "utils.py"]}')

        # 重新加载
        msgs = load_session_messages('test-session-001', session_dir)
        print(f'写入后重新加载: {len(msgs)} 条消息')
        for m in msgs:
            print(f'  [{m["role"]}] {str(m["content"])[:50]}')

        # 检查jsonl文件
        jsonl = session_dir / 'test-session-001.jsonl'
        events = jsonl.read_text(encoding='utf-8').strip().splitlines()
        print(f'\njsonl文件: {len(events)} 个事件')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    demo_compression()
    demo_token_budget()
    demo_memory()
    demo_session()
    print('\n全部验证通过')
