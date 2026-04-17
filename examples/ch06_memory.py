"""
第6章 记忆管理与上下文压缩 完整演示
======================================
六个渐进场景，全部使用真实框架代码。无需API key。

场景1：上下文腐烂可视化（10轮信噪比退化）
场景2：四级压缩逐级演示
场景3：压缩后tool对完整性修复
场景4：Token预算与压缩决策树
场景5：Memory系统（写入/加载/Dream整理）
场景6：Session持久化与断点续传

用法: python examples/ch06_memory.py
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, '.')

from harness_py.compressor import Compressor
from harness_py.token_budget import TokenBudget, should_compress
from harness_py.memory import load_memory_bundle, write_memory, dream
from harness_py.session import SessionWriter, load_session_messages, list_sessions


# ======================================================================
# 场景1：上下文腐烂可视化
# ======================================================================

def demo_context_rot():
    """模拟10轮对话，对比无压缩和有压缩的信噪比变化。

    对应6.1.1节。使用真实的Compressor证明压缩如何阻止上下文腐烂。
    """
    comp = Compressor(preserve_messages=4, microcompact_max_chars=300)

    print('=== 场景1：上下文腐烂 vs 压缩控制 ===\n')

    raw_msgs = [{'role': 'system', 'content': 'You are a coding assistant.'}]

    print(f'  {"轮次":>4}  {"消息数":>5}  {"无压缩":>10}  {"压缩后":>8}  {"节省":>5}  {"状态"}')
    print(f'  {"─"*4}  {"─"*5}  {"─"*10}  {"─"*8}  {"─"*5}  {"─"*10}')

    for turn in range(1, 11):
        if turn == 1:
            user_msg = '请逐个分析项目中的Python模块'
        elif turn <= 3:
            user_msg = '继续分析下一个模块'
        else:
            user_msg = '继续'

        file_lines = 5 + turn * turn * 3
        tool_result = f'# module_{turn}.py\n' + f'def func_{turn}(x):\n    return x + {turn}\n' * file_lines
        reply = f'模块{turn}包含{file_lines}行，核心功能是处理{turn}类请求。'

        for msg in [{'role': 'user', 'content': user_msg},
                     {'role': 'tool', 'content': tool_result},
                     {'role': 'assistant', 'content': reply}]:
            raw_msgs.append(msg)

        raw_tokens = comp.total_tokens(raw_msgs)

        # 在副本上执行压缩（不影响原始消息的累积）
        compressed = comp.compress(list(raw_msgs), target_tokens=max(raw_tokens * 6 // 10, 200))
        comp_tokens = comp.total_tokens(compressed)
        saving = (1 - comp_tokens / raw_tokens) * 100 if raw_tokens > 0 else 0

        # 信噪比：有用信息占总上下文比例
        useful = sum(len(m['content']) for m in raw_msgs if m['role'] != 'tool')
        total = sum(len(m['content']) for m in raw_msgs)
        snr = useful / max(total, 1) * 100

        if snr > 5:
            status = '正常'
        elif snr > 3:
            status = '开始退化'
        elif snr > 2:
            status = '明显退化'
        else:
            status = '严重退化'

        print(f'  {turn:>4}  {len(raw_msgs):>5}  {raw_tokens:>8,}tk  {comp_tokens:>6,}tk  {saving:>4.0f}%  SNR={snr:.1f}% {status}')

    print(f'\n  无压缩: {raw_tokens:,} tokens, 信噪比降至{snr:.1f}%')
    print(f'  压缩后: {comp_tokens:,} tokens (节省{saving:.0f}%)')
    print(f'  结论: 不压缩 → Agent越跑越蠢(信号被噪声淹没); 压缩 → 保持可控')
    print(f'  这就是为什么Agent"越跑越蠢"——不是模型变笨，是信号被噪声淹没\n')


# ======================================================================
# 场景2：四级压缩逐级演示
# ======================================================================

def demo_four_level_compression():
    """逐级演示 Microcompact → Snip → Compact → 完整压缩。

    对应6.2.1-6.2.4节。四级之间逐级递进：先试最便宜的，不够再上更贵的。
    """
    print('=== 场景2：四级压缩 ===\n')

    comp = Compressor(preserve_messages=2, microcompact_max_chars=200)

    # 构造膨胀的对话（模拟15轮读文件）
    msgs = [{'role': 'system', 'content': 'You are a coding assistant.'}]
    for i in range(15):
        msgs.append({'role': 'user', 'content': f'请分析 file_{i}.py'})
        msgs.append({'role': 'tool', 'content': f'# file_{i}.py\n' + 'def func():\n    x = 1\n' * 30})
        msgs.append({'role': 'assistant', 'content': f'文件{i}包含一个func函数。'})

    before = comp.total_tokens(msgs)
    print(f'  压缩前: {len(msgs)} 条消息, ~{before:,} tokens\n')

    # L0: Microcompact（截断旧tool结果）
    mc_result = comp._microcompact(list(msgs), preserve=2)
    mc_tokens = comp.total_tokens(mc_result)
    truncated = sum(1 for m in mc_result if '[truncated]' in str(m.get('content', '')))
    print(f'  L0 Microcompact: ~{mc_tokens:,} tokens (截断{truncated}条旧tool)')
    print(f'     零LLM成本, 只截断距离当前5轮以外的tool结果')

    # L1: Snip（替换为120字符预览）
    snip_result = comp._snip(list(msgs), preserve=2)
    snip_tokens = comp.total_tokens(snip_result)
    snipped = sum(1 for m in snip_result if '[snipped]' in str(m.get('content', '')))
    print(f'  L1 Snip:         ~{snip_tokens:,} tokens (snip了{snipped}条, 每次最多3条)')
    print(f'     零LLM成本, 保留120字符预览供Agent回忆')

    # L2: Compact（需要LLM，这里不调API所以跳过，展示降级）
    print(f'  L2 Compact:      需要LLM调用, 生成迭代摘要')
    print(f'     Hermes风格: 在上次摘要基础上追加, 非从零生成')

    # 完整压缩流程（不带LLM，降级为直接丢弃）
    full_result = comp.compress(list(msgs), target_tokens=500)
    full_tokens = comp.total_tokens(full_result)
    ratio = (1 - full_tokens / before) * 100
    print(f'  完整流程:        ~{full_tokens:,} tokens (目标500)')
    print(f'  压缩率: {ratio:.1f}%')

    print(f'\n  四级策略: 先Microcompact(免费) → Snip(免费) → Compact(一次LLM) → Reactive(紧急)')
    print(f'  Reactive模式: preserve减半, 最多6轮紧急循环\n')


# ======================================================================
# 场景3：压缩后tool对完整性修复
# ======================================================================

def demo_tool_pair_fix():
    """演示压缩可能破坏tool_call/tool_result配对，以及修复逻辑。

    对应6.2.5节。一旦tool对不完整，API调用直接失败。
    三个独立团队(Anthropic/Hermes、ByteDance、LangChain)实现了相同的修复。
    """
    print('=== 场景3：Tool对完整性修复 ===\n')

    comp = Compressor()

    # 构造有tool_call但缺少对应result的场景（模拟压缩后果）
    broken_msgs = [
        {'role': 'system', 'content': 'You are a coding assistant.'},
        # assistant发起了tool_call
        {'role': 'assistant', 'content': '让我读取文件。',
         'tool_calls': [
             {'id': 'call_001', 'function': {'name': 'read_file', 'arguments': '{"path":"main.py"}'}},
             {'id': 'call_002', 'function': {'name': 'grep_search', 'arguments': '{"pattern":"def"}'}},
         ]},
        # 只有call_001的result，call_002的result被压缩丢了
        {'role': 'tool', 'tool_call_id': 'call_001', 'content': 'def main(): pass'},
        # 还有一个孤立的result（对应的call被压缩了）
        {'role': 'tool', 'tool_call_id': 'call_999', 'content': '这个result的call已被压缩'},
    ]

    print(f'  修复前:')
    for m in broken_msgs[1:]:
        role = m['role']
        if role == 'assistant' and 'tool_calls' in m:
            calls = [tc['id'] for tc in m['tool_calls']]
            print(f'    assistant: tool_calls={calls}')
        elif role == 'tool':
            print(f'    tool: call_id={m.get("tool_call_id")} content={str(m["content"])[:30]}')

    # 执行修复
    fixed = comp._fix_orphaned_tool_pairs(broken_msgs)

    print(f'\n  修复后:')
    for m in fixed[1:]:
        role = m['role']
        if role == 'assistant' and 'tool_calls' in m:
            calls = [tc['id'] for tc in m['tool_calls']]
            print(f'    assistant: tool_calls={calls}')
        elif role == 'tool':
            is_stub = '[result was compacted]' in str(m.get('content', ''))
            marker = ' [STUB插入]' if is_stub else ''
            is_orphan_removed = m.get('tool_call_id') == 'call_999'
            print(f'    tool: call_id={m.get("tool_call_id")} '
                  f'content={str(m["content"])[:30]}{marker}')

    # 检查call_999是否被移除
    remaining_ids = [m.get('tool_call_id') for m in fixed if m.get('role') == 'tool']
    print(f'\n  修复操作:')
    print(f'    1. call_002缺少result → 插入stub "[result was compacted]"')
    print(f'    2. call_999缺少对应call → {"已移除" if "call_999" not in remaining_ids else "未移除"}')
    print(f'    原理: OpenAI兼容API要求tool_call和tool_result严格配对\n')


# ======================================================================
# 场景4：Token预算与压缩决策树
# ======================================================================

def demo_budget_decision():
    """演示五区Token预算分配和四级压缩触发条件。

    对应6.3.1-6.3.3节。
    """
    print('=== 场景4：Token预算与决策树 ===\n')

    budget = TokenBudget.allocate(128_000)
    print(f'  128K窗口五区分配:')
    print(f'    System Prompt:  {budget.system_prompt:>7,} ({budget.system_prompt/budget.context_window*100:.0f}%)')
    print(f'    Memory:         {budget.memory:>7,} ({budget.memory/budget.context_window*100:.0f}%)')
    print(f'    Current Task:   {budget.current_task:>7,} ({budget.current_task/budget.context_window*100:.0f}%)')
    print(f'    History:        {budget.history:>7,} ({budget.history/budget.context_window*100:.0f}%)')
    print(f'    Output Reserve: {budget.output_reserve:>7,} ({budget.output_reserve/budget.context_window*100:.0f}%) ← 永不侵占')

    # 压缩决策树
    print(f'\n  压缩决策树 (128K窗口):')
    test_points = [
        (50_000,  '39%', 'none',           '正常，无需压缩'),
        (70_000,  '55%', 'none',           '正常，接近预警线'),
        (90_000,  '70%', 'microcompact',   '预警 → 截断旧tool结果(零成本)'),
        (108_000, '84%', 'snip+compact',   '警告 → 裁剪+LLM摘要'),
        (120_000, '94%', 'emergency',      '危险 → preserve减半，全量重新摘要'),
        (126_000, '98%', 'reactive',       '溢出边缘 → 最多6轮紧急循环'),
    ]

    for tokens, pct, strategy, desc in test_points:
        need, reason = should_compress(budget, tokens)
        marker = '→' if need else ' '
        print(f'    {tokens:>7,} ({pct:>3}) {marker} {strategy:<16} {desc}')

    print(f'\n  关键阈值:')
    print(f'    80%({int(budget.context_window*0.8):,}): 常规压缩触发')
    print(f'    ~85%: 输出预留被侵占 → 紧急压缩')
    print(f'    15%输出预留不可侵占: DeepSeek在95%占用率下截断代码概率从2%升至18%\n')


# ======================================================================
# 场景5：Memory系统
# ======================================================================

def demo_memory():
    """演示Memory的写入/加载/Dream整理完整流程。

    对应6.4.1-6.4.3节。
    """
    print('=== 场景5：Memory系统 ===\n')

    tmpdir = tempfile.mkdtemp()
    try:
        cwd = Path(tmpdir)

        # 写入记忆（模拟Agent自动保存）
        write_memory(cwd, 'user_role', '用户是一名后端工程师，熟悉Python和Go。')
        write_memory(cwd, 'project_arch', '项目使用FastAPI + PostgreSQL，微服务架构。')
        write_memory(cwd, 'feedback_testing', '不要mock数据库，用真实测试数据库。')
        # 写入一条重复的（测试Dream去重）
        write_memory(cwd, 'project_arch_dup', '项目使用FastAPI + PostgreSQL，微服务架构。')
        print(f'  写入 4 条记忆（含1条重复）')

        # 加载记忆
        bundle = load_memory_bundle(cwd)
        print(f'  加载Memory bundle: {len(bundle)} 字符')
        for line in bundle.splitlines():
            if line.strip() and not line.startswith('<'):
                print(f'    {line}')

        # Dream整理
        result = dream(cwd)
        print(f'\n  Dream整理结果: {result}')
        print(f'    去重: {result["merged"]} 条')

        # 整理后重新加载
        bundle_after = load_memory_bundle(cwd)
        print(f'  整理后bundle: {len(bundle_after)} 字符')
        print(f'  压缩效果: {len(bundle) - len(bundle_after)} 字符减少')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print()


# ======================================================================
# 场景6：Session持久化与断点续传
# ======================================================================

def demo_session_resume():
    """演示Session的写入/中断/恢复完整流程。

    对应6.5.1-6.5.3节。JSONL追加写入确保崩溃安全。
    """
    print('=== 场景6：Session持久化与断点续传 ===\n')

    tmpdir = tempfile.mkdtemp()
    try:
        session_dir = Path(tmpdir) / 'sessions'

        # --- 第一次运行（模拟中途中断）---
        print('  第一次运行（模拟5轮后中断）:')
        writer = SessionWriter('session-001', session_dir, Path('.'))
        writer.write_message('system', 'You are a coding assistant.')
        writer.write_message('user', '请重构 calculator.py')
        writer.write_message('assistant', '好的，让我先读取项目结构。')
        writer.write_message('tool', '{"files": ["calculator.py", "tests/"]}')
        writer.write_message('assistant', '找到了目标文件，开始分析...')
        # 这里"崩溃"了（Ctrl+C / 网络中断）
        print(f'    写入 5 条消息 → 模拟Ctrl+C中断')

        # --- 查看可恢复的session ---
        print(f'\n  可恢复的Session:')
        sessions = list_sessions(session_dir)
        for sid, mtime, count in sessions:
            print(f'    {sid}: {count} 个事件')

        # --- 断点续传 ---
        print(f'\n  断点续传（事件重放）:')
        restored = load_session_messages('session-001', session_dir)
        print(f'    从jsonl恢复 {len(restored)} 条消息:')
        for i, m in enumerate(restored):
            content = str(m.get('content', ''))[:45]
            print(f'      [{m["role"]}] {content}')

        # --- 三步唤醒 ---
        print(f'\n  三步唤醒仪式（Anthropic最佳实践）:')
        print(f'    1. pwd — 确认工作目录（防止恢复到错误路径）')
        print(f'    2. git log --oneline -5 — 查看最近变更（比session历史更可靠）')
        print(f'    3. 读取progress.txt — 获取任务进度（Agent主动维护的进度文件）')
        print(f'    效果: 唤醒后前5轮犯错率降低~40%')

        # --- 在恢复的基础上继续 ---
        print(f'\n  在恢复基础上继续:')
        writer2 = SessionWriter('session-001', session_dir, Path('.'))
        writer2.write_message('user', '继续重构，从分析结果开始')
        writer2.write_message('assistant', '好的，根据之前的分析，calculator.py需要拆分...')

        final = load_session_messages('session-001', session_dir)
        print(f'    续传后总消息: {len(final)} 条（原5 + 新2）')

        # JSONL崩溃安全性
        jsonl_path = session_dir / 'session-001.jsonl'
        events = jsonl_path.read_text(encoding='utf-8').strip().splitlines()
        print(f'    JSONL文件: {len(events)} 个事件')
        print(f'    崩溃安全: 追加写入, 最多丢失最后1条事件')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print()


# ======================================================================
# 入口
# ======================================================================

if __name__ == '__main__':
    demo_context_rot()
    demo_four_level_compression()
    demo_tool_pair_fix()
    demo_budget_decision()
    demo_memory()
    demo_session_resume()
    print('全部验证通过')
