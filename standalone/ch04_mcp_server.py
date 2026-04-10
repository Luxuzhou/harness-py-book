"""
Ch4 MCP Server 最小示例
========================
演示如何用MCP协议将一个SQLite数据库暴露为Agent可调用的工具。

这是一个教学示例，展示MCP Server的核心概念：
1. 工具注册（声明schema）
2. 工具执行（处理调用）
3. 传输层（stdio通信）

用法：
  作为MCP Server启动：python standalone/ch04_mcp_server.py
  测试模式（不需要MCP Client）：python standalone/ch04_mcp_server.py --test

MCP协议参考：https://modelcontextprotocol.io
"""

import json
import sys
import sqlite3
import tempfile
from pathlib import Path


# ============ 数据库层 ============

def init_db(db_path: str) -> sqlite3.Connection:
    """初始化示例数据库。"""
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn


# ============ 工具定义 ============

TOOLS = [
    {
        'name': 'list_notes',
        'description': '列出所有笔记。返回id、标题和创建时间。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'limit': {
                    'type': 'integer',
                    'description': '最多返回多少条（默认20）',
                },
            },
        },
    },
    {
        'name': 'add_note',
        'description': '添加一条新笔记。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string', 'description': '笔记标题'},
                'content': {'type': 'string', 'description': '笔记内容'},
            },
            'required': ['title'],
        },
    },
    {
        'name': 'search_notes',
        'description': '按关键词搜索笔记标题和内容。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'keyword': {'type': 'string', 'description': '搜索关键词'},
            },
            'required': ['keyword'],
        },
    },
]


# ============ 工具执行 ============

def handle_tool_call(conn: sqlite3.Connection, name: str, args: dict) -> str:
    """
    处理工具调用。

    这是MCP Server的核心：根据工具名路由到对应的处理函数。
    每个处理函数操作数据库并返回文本结果。
    """
    if name == 'list_notes':
        limit = args.get('limit', 20)
        rows = conn.execute(
            'SELECT id, title, created_at FROM notes ORDER BY id DESC LIMIT ?',
            (limit,),
        ).fetchall()
        if not rows:
            return '暂无笔记'
        lines = [f'#{r[0]} {r[1]} ({r[2]})' for r in rows]
        return f'共 {len(rows)} 条笔记:\n' + '\n'.join(lines)

    elif name == 'add_note':
        title = args.get('title', '')
        content = args.get('content', '')
        if not title:
            return '错误: 标题不能为空'
        cursor = conn.execute(
            'INSERT INTO notes (title, content) VALUES (?, ?)',
            (title, content),
        )
        conn.commit()
        return f'已添加笔记 #{cursor.lastrowid}: {title}'

    elif name == 'search_notes':
        keyword = args.get('keyword', '')
        if not keyword:
            return '错误: 关键词不能为空'
        rows = conn.execute(
            'SELECT id, title, content FROM notes WHERE title LIKE ? OR content LIKE ?',
            (f'%{keyword}%', f'%{keyword}%'),
        ).fetchall()
        if not rows:
            return f'未找到包含 "{keyword}" 的笔记'
        lines = [f'#{r[0]} {r[1]}: {r[2][:50]}' for r in rows]
        return f'找到 {len(rows)} 条:\n' + '\n'.join(lines)

    else:
        return f'未知工具: {name}'


# ============ MCP协议层（stdio传输） ============

def run_mcp_server(conn: sqlite3.Connection):
    """
    MCP Server主循环（stdio传输）。

    MCP协议基于JSON-RPC 2.0，通过stdin/stdout通信：
    - Client发送请求 → Server处理 → Server返回响应
    - 三种关键方法：initialize, tools/list, tools/call

    这是最小实现，生产环境应使用官方SDK。
    """
    def send_response(id, result):
        resp = json.dumps({'jsonrpc': '2.0', 'id': id, 'result': result})
        # MCP使用Content-Length头 + 空行 + body的格式
        header = f'Content-Length: {len(resp.encode("utf-8"))}\r\n\r\n'
        sys.stdout.write(header + resp)
        sys.stdout.flush()

    def send_error(id, code, message):
        resp = json.dumps({
            'jsonrpc': '2.0', 'id': id,
            'error': {'code': code, 'message': message},
        })
        header = f'Content-Length: {len(resp.encode("utf-8"))}\r\n\r\n'
        sys.stdout.write(header + resp)
        sys.stdout.flush()

    sys.stderr.write('[MCP] Notes Server started\n')

    buffer = ''
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            # 简化的解析：跳过Content-Length头，直接找JSON
            line = line.strip()
            if not line or line.startswith('Content-Length'):
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                buffer += line
                try:
                    request = json.loads(buffer)
                    buffer = ''
                except json.JSONDecodeError:
                    continue

            method = request.get('method', '')
            req_id = request.get('id')
            params = request.get('params', {})

            if method == 'initialize':
                send_response(req_id, {
                    'protocolVersion': '2024-11-05',
                    'serverInfo': {'name': 'notes-server', 'version': '1.0.0'},
                    'capabilities': {'tools': {}},
                })

            elif method == 'tools/list':
                send_response(req_id, {'tools': TOOLS})

            elif method == 'tools/call':
                tool_name = params.get('name', '')
                tool_args = params.get('arguments', {})
                result_text = handle_tool_call(conn, tool_name, tool_args)
                send_response(req_id, {
                    'content': [{'type': 'text', 'text': result_text}],
                })

            elif method == 'notifications/initialized':
                pass  # 客户端确认，无需响应

            else:
                if req_id is not None:
                    send_error(req_id, -32601, f'Method not found: {method}')

        except KeyboardInterrupt:
            break
        except Exception as e:
            sys.stderr.write(f'[MCP] Error: {e}\n')


# ============ 测试模式 ============

def run_test():
    """不需要MCP Client的独立测试。"""
    print('=== Ch4 MCP Server 测试模式 ===\n')

    db_path = Path(tempfile.mkdtemp()) / 'notes.db'
    conn = init_db(str(db_path))
    print(f'数据库: {db_path}\n')

    # 展示工具schema
    print('已注册工具:')
    for tool in TOOLS:
        params = list(tool['inputSchema'].get('properties', {}).keys())
        required = tool['inputSchema'].get('required', [])
        print(f'  {tool["name"]}({", ".join(params)})')
        print(f'    描述: {tool["description"]}')
        print(f'    必填: {required}')
    print()

    # 模拟Agent调用
    calls = [
        ('add_note', {'title': 'Agent架构笔记', 'content': '六层架构：约束→工具→上下文→记忆→验证→编排'}),
        ('add_note', {'title': '压缩策略', 'content': '四级：Microcompact→Snip→Compact→Reactive'}),
        ('add_note', {'title': 'MCP协议', 'content': 'JSON-RPC 2.0 over stdio，三种方法：initialize/tools/list/tools/call'}),
        ('list_notes', {'limit': 10}),
        ('search_notes', {'keyword': '架构'}),
        ('search_notes', {'keyword': '不存在的关键词'}),
    ]

    for name, args in calls:
        print(f'→ {name}({args})')
        result = handle_tool_call(conn, name, args)
        print(f'  {result}\n')

    conn.close()
    print('=== MCP Server 核心概念 ===')
    print('1. 工具注册: TOOLS列表定义name/description/inputSchema')
    print('2. 工具执行: handle_tool_call路由到具体处理函数')
    print('3. 传输层: JSON-RPC 2.0 over stdio (Client <-> Server)')
    print('4. 每个MCP Server = 一组工具 + 一个数据源')
    print()
    print('在Agent中集成MCP Server时，每个Server的工具schema')
    print(f'会占用约 {sum(len(json.dumps(t)) for t in TOOLS) // 4} tokens。')
    print('Stripe的经验：500+工具时需要精选子集，避免token浪费。')


if __name__ == '__main__':
    if '--test' in sys.argv:
        run_test()
    else:
        db_path = Path(tempfile.mkdtemp()) / 'notes.db'
        conn = init_db(str(db_path))
        run_mcp_server(conn)
