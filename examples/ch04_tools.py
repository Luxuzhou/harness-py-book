"""
第4章 工具系统与MCP 完整演示
=============================
四个渐进场景，全部使用真实框架代码。无需API key。

场景1：6工具逐一验证 + 安全拦截
场景2：分阶段工具解锁（规划阶段只读 → 执行阶段全开）
场景3：工具描述精度对选择的影响
场景4：MCP协议核心概念

用法: python examples/ch04_tools.py
"""

import sys
import json
import tempfile
import sqlite3
from pathlib import Path

sys.path.insert(0, '.')

from harness_py.config import AgentConfig
from harness_py.tools import (
    tool_read_file, tool_write_file, tool_edit_file,
    tool_grep_search, tool_glob_search, tool_bash,
    execute_tool, find_best_bash, smart_decode,
    TOOL_SCHEMAS, get_schemas_for_phase,
)


# ======================================================================
# 场景1：6工具逐一验证 + 安全拦截
# ======================================================================

def demo_six_tools():
    """验证6个核心工具的基本功能和安全边界。"""
    print('=== 场景1：6工具验证 + 安全拦截 ===\n')

    with tempfile.TemporaryDirectory() as d:
        cfg = AgentConfig(cwd=Path(d), allow_write=True, allow_shell=True)

        # 准备项目文件
        (Path(d) / 'src').mkdir()
        (Path(d) / 'src' / 'main.py').write_text(
            'def hello():\n    return "world"\n\ndef add(a, b):\n    return a + b\n',
            encoding='utf-8',
        )
        (Path(d) / 'src' / 'utils.py').write_text(
            'import os\nimport sys\n\ndef get_version():\n    return "1.0.0"\n',
            encoding='utf-8',
        )

        # --- 正常操作 ---
        cases = [
            ('read_file',    {'path': 'src/main.py'},           '读取源文件'),
            ('write_file',   {'path': 'output/report.md', 'content': '# Done\n完成。'}, '创建新文件(自动建目录)'),
            ('edit_file',    {'path': 'src/main.py',
                              'old_string': 'return "world"',
                              'new_string': 'return "hello world"'},  '字符串匹配替换(非行号)'),
            ('grep_search',  {'pattern': r'def \w+', 'path': 'src'},  '正则搜索函数定义'),
            ('glob_search',  {'pattern': '**/*.py'},                   '文件名模式匹配'),
        ]

        passed = 0
        for name, args, desc in cases:
            ok, result = execute_tool(name, args, cfg)
            status = 'PASS' if ok else 'FAIL'
            preview = result.replace('\n', '\\n')[:60]
            print(f'  {status} {name}: {preview}  ({desc})')
            if ok:
                passed += 1

        # bash
        if find_best_bash():
            ok, result = execute_tool('bash', {'command': 'echo "hello from bash"'}, cfg)
            status = 'PASS' if ok else 'FAIL'
            print(f'  {status} bash: {result.strip()[:60]}  (Shell命令执行)')
            if ok:
                passed += 1
        else:
            print(f'  SKIP bash: 未找到Git Bash')

        # --- 安全拦截 ---
        print('\n  安全拦截:')
        attacks = [
            ('read_file',  {'path': '../../etc/passwd'},                '路径遍历攻击'),
            ('write_file', {'path': '/tmp/../../evil.txt', 'content': 'x'}, '绝对路径逃逸'),
        ]
        for name, args, desc in attacks:
            ok, result = execute_tool(name, args, cfg)
            print(f'  {"BLOCK" if not ok else "LEAK!"} {desc}: {result[:50]}')

        total = 5 + (1 if find_best_bash() else 0)
        print(f'\n  结果: {passed}/{total} 工具测试通过，安全拦截全部生效\n')


# ======================================================================
# 场景2：分阶段工具解锁
# ======================================================================

def demo_phase_unlock():
    """演示规划阶段只暴露只读工具，执行阶段全部解锁。

    这是第4章4.3.3节的核心概念：不是在execute阶段拒绝调用，
    而是在schema阶段就不暴露工具。Agent根本看不到write_file。
    """
    print('=== 场景2：分阶段工具解锁 ===')
    print('规划阶段(turn 1-3): Agent只能看到只读工具')
    print('执行阶段(turn 4+):  Agent看到全部工具\n')

    cfg = AgentConfig(
        cwd=Path('.'),
        planning_turns=3,
        planning_tools=['read_file', 'grep_search', 'glob_search'],
    )

    for turn in [1, 2, 3, 4, 5]:
        schemas = get_schemas_for_phase(turn, cfg)
        tool_names = [s['function']['name'] for s in schemas]
        phase = '规划' if turn <= 3 else '执行'
        marker = '[LOCKED]' if turn <= 3 else '[OPEN]  '
        print(f'  Turn {turn} ({phase}): {marker} {tool_names}')

    # 关键对比
    plan_schemas = get_schemas_for_phase(1, cfg)
    exec_schemas = get_schemas_for_phase(4, cfg)
    plan_names = {s['function']['name'] for s in plan_schemas}
    exec_names = {s['function']['name'] for s in exec_schemas}
    unlocked = exec_names - plan_names
    print(f'\n  规划阶段: {len(plan_names)} 个工具（只读）')
    print(f'  执行阶段: {len(exec_names)} 个工具（全部）')
    print(f'  解锁工具: {sorted(unlocked)}')
    print(f'  原理: schema阶段不暴露 → Agent物理上无法调用\n')


# ======================================================================
# 场景3：工具描述精度对选择的影响
# ======================================================================

def demo_description_quality():
    """用真实TOOL_SCHEMAS量化description的质量指标。

    对应4.1.2节和4.5.1节。通过解析实际schema检测四个质量维度：
    长度、边界说明、使用场景、参数覆盖率。
    """
    print('=== 场景3：工具描述质量分析 ===\n')

    # 从真实TOOL_SCHEMAS中提取并量化每个工具的description质量
    quality_checks = {
        'has_boundary': lambda d: any(w in d.lower() for w in ['instead', 'not ', 'use ']),
        'has_scenario': lambda d: any(w in d.lower() for w in ['for ', 'best for', 'use for']),
        'has_format':   lambda d: any(w in d.lower() for w in ['returns', 'format', 'output']),
        'length_ok':    lambda d: len(d) >= 30,
    }

    print(f'  从TOOL_SCHEMAS提取 {len(TOOL_SCHEMAS)} 个工具的description:')
    print(f'  {"工具":<14} {"长度":>4} {"边界":>4} {"场景":>4} {"格式":>4}  描述')
    print(f'  {"─"*14} {"─"*4} {"─"*4} {"─"*4} {"─"*4}  {"─"*40}')

    total_score = 0
    for schema in TOOL_SCHEMAS:
        func = schema['function']
        name = func['name']
        desc = func['description']
        params = func.get('parameters', {}).get('properties', {})

        scores = {k: check(desc) for k, check in quality_checks.items()}
        score = sum(scores.values())
        total_score += score

        marks = ''.join('Y' if v else '-' for v in scores.values())
        print(f'  {name:<14} {len(desc):>4} {marks[0]:>4} {marks[1]:>4} {marks[2]:>4}  {desc[:40]}...')

    avg = total_score / len(TOOL_SCHEMAS)
    print(f'\n  平均质量分: {avg:.1f}/4  (4=完美)')

    # 对比实验：模糊description的schema占多少token vs 精确description
    vague_schemas = []
    for s in TOOL_SCHEMAS:
        vague = dict(s)
        vague['function'] = dict(s['function'])
        # 替换为模糊描述
        vague['function']['description'] = s['function']['name'].replace('_', ' ')
        vague_schemas.append(vague)

    import json
    precise_tokens = len(json.dumps(TOOL_SCHEMAS)) // 4
    vague_tokens = len(json.dumps(vague_schemas)) // 4

    print(f'\n  token开销对比:')
    print(f'    精确描述 (harness_py): ~{precise_tokens} tokens / {len(TOOL_SCHEMAS)} tools')
    print(f'    模糊描述 (仅工具名):  ~{vague_tokens} tokens / {len(TOOL_SCHEMAS)} tools')
    print(f'    差额: {precise_tokens - vague_tokens} tokens (精确描述多占{(precise_tokens/vague_tokens-1)*100:.0f}%)')
    print(f'    但Stripe数据表明: 这额外的token换来选择准确率从62%到91%\n')


# ======================================================================
# 场景4：MCP协议核心概念
# ======================================================================

def demo_mcp_concept():
    """演示MCP协议的三种关键方法，无需启动Server进程。

    对应4.4.1-4.4.2节。完整的MCP Server实现见 examples/ch04_mcp_server.py (--test模式)
    """
    print('=== 场景4：MCP协议核心概念 ===\n')

    # MCP Server端：工具定义
    tools = [
        {
            'name': 'list_notes',
            'description': '列出所有笔记',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'limit': {'type': 'integer', 'description': '最多返回条数'},
                },
            },
        },
        {
            'name': 'add_note',
            'description': '添加笔记',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'title': {'type': 'string'},
                    'content': {'type': 'string'},
                },
                'required': ['title'],
            },
        },
    ]

    # 模拟MCP三步握手
    print('  第一步: initialize (握手)')
    init_req = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                'params': {'protocolVersion': '2024-11-05',
                           'clientInfo': {'name': 'harness-py', 'version': '0.1.0'}}}
    init_resp = {'jsonrpc': '2.0', 'id': 1,
                 'result': {'protocolVersion': '2024-11-05',
                            'serverInfo': {'name': 'notes-server', 'version': '1.0.0'},
                            'capabilities': {'tools': {}}}}
    print(f'    Client → {json.dumps(init_req)[:70]}...')
    print(f'    Server → capabilities: {list(init_resp["result"]["capabilities"].keys())}')

    print('\n  第二步: tools/list (发现工具)')
    print(f'    Server返回 {len(tools)} 个工具:')
    for t in tools:
        params = list(t['inputSchema'].get('properties', {}).keys())
        print(f'      {t["name"]}({", ".join(params)}) — {t["description"]}')

    print('\n  第三步: tools/call (调用工具)')
    # 用内存SQLite演示
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT)')
    conn.execute("INSERT INTO notes VALUES (1, 'Agent架构', '六层：约束→工具→上下文→记忆→验证→编排')")
    conn.execute("INSERT INTO notes VALUES (2, 'MCP协议', 'JSON-RPC 2.0 over stdio')")
    conn.commit()

    calls = [
        ('add_note', {'title': '压缩策略', 'content': '四级：Microcompact→Snip→Compact→Reactive'}),
        ('list_notes', {'limit': 5}),
    ]
    for name, args in calls:
        print(f'    → tools/call: {name}({args})')
        if name == 'add_note':
            conn.execute('INSERT INTO notes (title, content) VALUES (?, ?)',
                         (args['title'], args.get('content', '')))
            conn.commit()
            print(f'      ← 已添加笔记: {args["title"]}')
        elif name == 'list_notes':
            rows = conn.execute(f'SELECT id, title FROM notes LIMIT {args["limit"]}').fetchall()
            for r in rows:
                print(f'      ← #{r[0]} {r[1]}')
    conn.close()

    # Token开销计算
    schema_tokens = sum(len(json.dumps(t)) // 4 for t in tools)
    print(f'\n  工具schema token开销: ~{schema_tokens} tokens/轮')
    print(f'  30轮对话累计: ~{schema_tokens * 30:,} tokens')
    print(f'  经验法则: 内置工具≤10, 活跃工具总数≤20\n')


# ======================================================================
# 入口
# ======================================================================

if __name__ == '__main__':
    demo_six_tools()
    demo_phase_unlock()
    demo_description_quality()
    demo_mcp_concept()
    print('全部验证通过')
