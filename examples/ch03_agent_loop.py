"""
第3章 最小Agent循环 + 安全实验
==============================
演示30行Agent循环和三轮安全约束迭代。
需要API key运行完整循环，但安全实验部分无需API。

用法: python examples/ch03_agent_loop.py
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path

# 加载.env文件（如果存在）
_env_file = Path(__file__).parent.parent / '.env'
if _env_file.exists():
    import os
    for line in _env_file.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

from harness_py.config import AgentConfig


def demo_safety_layers():
    """三轮安全实验（无需API）。"""
    print('=== 三轮安全实验 ===\n')

    # 第一轮：零约束
    print('第一轮：零约束')
    dangerous_commands = [
        'rm -rf /tmp/important',
        'cat /etc/shadow',
        'python -c "import shutil; shutil.rmtree(\'/data\')"',
    ]
    for cmd in dangerous_commands:
        print(f'  Agent请求执行: {cmd}')
        print(f'  结果: 允许（无任何检查）')
    print(f'  结论: 全部放行，Agent可以做任何事\n')

    # 第二轮：路径白名单 + 命令黑名单
    print('第二轮：路径白名单 + 命令黑名单')
    WRITABLE = ['src/', 'tests/']
    BLOCKED = ['rm -rf', 'rmdir /s', 'format ']

    test_cases = [
        ('write_file', 'src/main.py', True, '在白名单内'),
        ('write_file', '/etc/passwd', False, '不在白名单内'),
        ('bash', 'rm -rf /', False, '命令黑名单拦截'),
        ('bash', 'python -c "import os; os.remove(\'src/data.db\')"', True, '间接绕过！'),
    ]
    for tool, arg, allowed, reason in test_cases:
        status = 'ALLOW' if allowed else 'BLOCK'
        print(f'  {tool}({arg[:40]}) -> {status} ({reason})')
    print(f'  结论: Agent通过写脚本+执行脚本绕过了路径检查\n')

    # 第三轮：+ 内容扫描（使用框架的安全检查）
    print('第三轮：+ 路径安全检查（框架级）')
    from harness_py.tools import _check_path_escape
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        ac = AgentConfig(cwd=Path(d))
        attacks = [
            ('正常路径', 'src/main.py', True),
            ('路径遍历', '../../etc/passwd', False),
            ('绝对路径', '/etc/shadow', False),
        ]
        for name, path, should_ok in attacks:
            ok, reason = _check_path_escape(ac, path)
            status = 'ALLOW' if ok else 'BLOCK'
            expected = 'OK' if ok == should_ok else 'UNEXPECTED!'
            print(f'  {name}: {path} -> {status} [{expected}]')
    print(f'  结论: 路径遍历和绝对路径攻击被框架级检查拦截')


def demo_minimal_loop():
    """最小Agent循环（需要API key）。"""
    from harness_py import run, ModelConfig, AgentConfig

    mc = ModelConfig.from_env()
    if not mc.api_key:
        print('\n[跳过] 最小循环演示需要设置OPENAI_API_KEY或HARNESS_API_KEY环境变量')
        return

    print('\n=== 最小Agent循环 ===')
    result = run(
        '列出当前目录下的所有.py文件，并统计总行数。',
        model_config=mc,
        agent_config=AgentConfig(cwd=Path('.'), max_iterations=10, planning_turns=1),
    )
    print(f'结果: {result.turns}轮, {result.tool_calls}工具调用, stop={result.stop_reason}')


if __name__ == '__main__':
    demo_safety_layers()
    demo_minimal_loop()
