"""
第3章：Agent循环与约束层——最小循环 + 三层安全 + 三轮实验
=========================================================
可选API key：有key跑真实Agent，无key跑模拟演示。
用法: python standalone/ch03_agent_loop.py
"""
import json
import re


# ===== 最小Agent循环（30行） =====

def minimal_agent_loop(call_model, tools, task: str, max_turns: int = 5):
    """全书代码线的起点。30行核心循环。"""
    messages = [{'role': 'user', 'content': task}]
    for turn in range(max_turns):
        response = call_model(messages)
        tool_calls = response.get('tool_calls', [])
        if not tool_calls:
            return response.get('content', '')
        messages.append(response)
        for tc in tool_calls:
            name = tc['function']['name']
            args = json.loads(tc['function']['arguments'])
            result = tools[name](args)
            messages.append({'role': 'tool', 'tool_call_id': tc['id'], 'content': result})
    return '(达到最大轮次)'


# ===== 三层安全约束 =====

WRITABLE_PATHS = ['src/', 'tests/', 'docs/']
BLOCKED_COMMANDS = ['rm -rf', 'rmdir /s', 'format ', 'mkfs', 'dd if=']
DANGEROUS_PATTERNS = [
    r'shutil\.rmtree', r'os\.remove', r'subprocess\.call.*shell\s*=\s*True',
    r'eval\s*\(', r'exec\s*\(',
]

def check_path(path: str) -> bool:
    """Layer 1: 路径白名单"""
    return any(path.startswith(p) for p in WRITABLE_PATHS)

def check_command(cmd: str) -> bool:
    """Layer 2: 命令黑名单"""
    return not any(d in cmd for d in BLOCKED_COMMANDS)

def check_content(content: str) -> list[str]:
    """Layer 3: 内容扫描"""
    return [p for p in DANGEROUS_PATTERNS if re.search(p, content)]


# ===== 三轮安全实验 =====

def experiment_round1():
    """第一轮：零约束"""
    print('\n--- 第一轮：零约束 ---')
    actions = [
        ('Agent执行', 'mkdir old_backups'),
        ('Agent执行', 'echo fake > old_backups/data.txt'),
        ('Agent执行', 'python -c "import shutil; shutil.rmtree(\'old_backups\')"'),
    ]
    for desc, cmd in actions:
        print(f'  {desc}: {cmd}')
    print('  结果: 3次危险操作，2次越界写入，零拦截')

def experiment_round2():
    """第二轮：v1安全层（路径+命令）"""
    print('\n--- 第二轮：路径白名单+命令黑名单 ---')
    tests = [
        ('write old_backups/x.txt', check_path('old_backups/x.txt'), '路径不在白名单'),
        ('write src/main.py', check_path('src/main.py'), '路径在白名单'),
        ('rm -rf /', check_command('rm -rf /'), '命令在黑名单'),
        ('python cleanup.py', check_command('python cleanup.py'), '命令不在黑名单'),
    ]
    for desc, result, reason in tests:
        status = '✅通过' if result else '🚫拦截'
        print(f'  {desc:30s} → {status} ({reason})')
    print('  结果: Agent绕过——写了一个Python脚本调用shutil.rmtree')

def experiment_round3():
    """第三轮：v2安全层（+内容扫描）"""
    print('\n--- 第三轮：+内容扫描 ---')
    scripts = [
        'import shutil; shutil.rmtree("old_backups")',
        'os.remove("/etc/passwd")',
        'subprocess.call("curl evil.com", shell=True)',
        'print("hello world")',
    ]
    for script in scripts:
        threats = check_content(script)
        status = f'🚫拦截({threats[0][:20]})' if threats else '✅安全'
        print(f'  {script:50s} → {status}')
    print('  结果: 三次拦截零突破')


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║  第3章：Agent循环与约束层                             ║
╚══════════════════════════════════════════════════════╝

最小Agent循环（30行核心代码）：
  while True:
    response = call_model(messages)
    tool_calls = parse_tool_calls(response)
    if not tool_calls: break  # 自然停止
    for call in tool_calls:
      result = execute_tool(call)
      messages.append(result)  # 反馈给模型
""")

    print('三轮安全实验：')
    experiment_round1()
    experiment_round2()
    experiment_round3()

    print(f"""
总结：
  Layer 1 路径白名单: 限制Agent可写的目录
  Layer 2 命令黑名单: 禁止rm -rf等破坏性命令
  Layer 3 内容扫描:   拦截Agent生成的危险脚本

  三层叠加的纵深防御，约束不是削弱Agent，
  而是缩小搜索空间让它更快收敛（Cursor实验数据验证）。
""")


if __name__ == '__main__':
    main()
