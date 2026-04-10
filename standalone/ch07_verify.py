"""
第7章：验证与对抗式评估——LoopGuard + 分阶段规划演示
===================================================
不需要API key。演示死循环检测和工具分阶段解锁。
用法: python standalone/ch07_verify.py
"""

def demo_loop_guard():
    """演示LoopGuard的四种检测场景。"""
    print('=== LoopGuard循环守卫 ===\n')

    # 简化版LoopGuard
    recent = []
    errors = 0
    streak = 0
    last_tool = ''

    scenarios = [
        # (tool_name, args_sig, ok, result_preview, description)
        ('bash', 'echo_hi', True, 'hello', '正常调用'),
        ('bash', 'echo_hi', True, 'hello', '相同调用（2/3）'),
        ('bash', 'echo_hi', True, 'hello', '相同调用（3/3）→ 检测到死循环'),
        ('read_file', 'main.py', True, 'def main():', '换了工具，重置'),
        ('bash', 'pytest', False, 'error', '失败1'),
        ('bash', 'pytest_v', False, 'error', '失败2'),
        ('bash', 'pytest_vv', False, 'error', '失败3'),
        ('bash', 'pytest_x', False, 'error', '失败4'),
        ('bash', 'pytest_xx', False, 'error', '连续失败5次 → 熔断'),
    ]

    for tool, sig, ok, preview, desc in scenarios:
        # 重复检测
        call_sig = f'{tool}:{sig}:{preview}'
        recent.append(call_sig)
        if len(recent) > 10:
            recent = recent[-10:]

        intervene = False
        reason = ''

        # 检测1：连续相同
        if len(recent) >= 3 and len(set(recent[-3:])) == 1:
            intervene = True
            reason = '死循环：最近3次完全相同'

        # 检测2：连续错误
        if not ok:
            errors += 1
            if errors >= 5:
                intervene = True
                reason = f'连续{errors}次失败'
        else:
            errors = 0

        status = f'🚨 {reason}' if intervene else '✅ 正常'
        print(f'  {desc:30s} → {status}')


def demo_planning_phase():
    """演示分阶段工具解锁。"""
    print('\n=== 分阶段工具解锁 ===\n')

    all_tools = ['read_file', 'write_file', 'edit_file', 'grep_search', 'glob_search', 'bash']
    planning_tools = ['read_file', 'grep_search', 'glob_search']
    planning_turns = 3

    for turn in range(1, 7):
        if turn <= planning_turns:
            available = planning_tools
            phase = '📖 规划阶段'
        else:
            available = all_tools
            phase = '🔧 执行阶段'

        blocked = [t for t in all_tools if t not in available]
        print(f'  Turn {turn}: {phase}')
        print(f'    可用: {", ".join(available)}')
        if blocked:
            print(f'    禁用: {", ".join(blocked)}')
        if turn == planning_turns:
            print(f'    ──── 规划结束，下轮解锁全部工具 ────')

    print(f"""
  设计原理：
    不是prompt里写"请先规划"（模型可以忽略）
    而是前{planning_turns}轮根本没有write_file/edit_file/bash可用（物理限制）
    Agent被迫用只读工具理解代码，输出修改计划
    第{planning_turns+1}轮起解锁全部工具，按计划执行

  实测效果（CostTracker任务）：
    无规划：30轮用完，没来得及写测试
    有规划：30轮内完成修改+测试+总结报告
""")


def demo_verification_loop():
    """演示闭环验证。"""
    print('=== 闭环验证 ===\n')
    print('  开环（不验证）:')
    print('    Agent修改代码 → 报告"完成" → 信了')
    print('    问题：model_name属性不存在，下次运行才发现\n')
    print('  闭环（Harness独立验证）:')
    print('    Agent修改代码 → 报告"完成" → Harness跑pytest → 发现bug → 要求Agent修复')
    print('    关键：pytest不是Agent调用的，是Harness框架自己调用的')
    print('    "做事的和验证的分离，不信Agent的自我评价"\n')


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║  第7章：验证与对抗式评估                              ║
╚══════════════════════════════════════════════════════╝
""")
    demo_loop_guard()
    demo_planning_phase()
    demo_verification_loop()


if __name__ == '__main__':
    main()
