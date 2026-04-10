"""
第7章 验证与对抗式评估演示
============================
LoopGuard四种检测 + 分阶段工具解锁。直接调用harness_py模块。

用法: python examples/ch07_verify.py
"""

import sys
sys.path.insert(0, '.')

from harness_py.loop_guard import LoopGuard
from harness_py.tools import get_schemas_for_phase
from harness_py.config import AgentConfig


def demo_loop_guard():
    """LoopGuard四种检测。"""
    print('=== LoopGuard 四种检测 ===\n')

    # 检测1: 相同调用重复
    print('检测1: 相同调用重复')
    g = LoopGuard(max_identical_calls=3)
    for i in range(3):
        ok, msg = g.check('bash', {'cmd': 'echo hi'}, True, 'hello')
        if ok:
            print(f'  第{i+1}次: 介入! {msg[:50]}')
        else:
            print(f'  第{i+1}次: 正常')

    # 检测2: 连续错误
    print('\n检测2: 连续错误累积')
    g = LoopGuard(max_consecutive_errors=3)
    for i in range(3):
        ok, msg = g.check('bash', {'cmd': f'cmd_{i}'}, False, 'error')
        if ok:
            print(f'  第{i+1}次失败: 介入! {msg[:50]}')
        else:
            print(f'  第{i+1}次失败: 继续')

    # 检测3: 成功重置错误计数
    print('\n检测3: 成功重置错误计数')
    g = LoopGuard(max_consecutive_errors=3)
    g.check('bash', {'cmd': '1'}, False, 'err')
    g.check('bash', {'cmd': '2'}, False, 'err')
    g.check('bash', {'cmd': '3'}, True, 'ok')  # 成功，重置
    ok, _ = g.check('bash', {'cmd': '4'}, False, 'err')
    print(f'  2次失败→1次成功→1次失败: 介入={ok} (应为False，因为计数已重置)')

    # 检测4: 同工具连续使用
    print('\n检测4: 同工具连续使用')
    g = LoopGuard(max_same_tool_streak=3)
    g.check('bash', {'cmd': '1'}, True, 'a')
    g.check('bash', {'cmd': '2'}, True, 'b')
    ok, msg = g.check('bash', {'cmd': '3'}, True, 'c')
    print(f'  bash连续3次: 介入={ok} {msg[:50] if ok else ""}')

    # 检测4b: 换工具重置streak
    g2 = LoopGuard(max_same_tool_streak=3)
    g2.check('bash', {}, True, 'a')
    g2.check('bash', {}, True, 'b')
    g2.check('read_file', {}, True, 'c')  # 换了工具
    ok, _ = g2.check('bash', {}, True, 'd')
    print(f'  bash→bash→read→bash: 介入={ok} (应为False，streak已重置)')

    # 检测5: 总量限制
    print('\n检测5: 总量限制')
    g = LoopGuard(max_total_tool_calls=5)
    for i in range(6):
        ok, msg = g.check(f'tool_{i}', {}, True, f'r{i}')
        if ok:
            print(f'  第{i+1}次: 介入! {msg[:50]}')


def demo_planning_phase():
    """分阶段工具解锁。"""
    print('\n=== 分阶段工具解锁 ===\n')

    ac = AgentConfig(planning_turns=3)

    for turn in [1, 2, 3, 4, 5]:
        schemas = get_schemas_for_phase(turn, ac)
        names = [s['function']['name'] for s in schemas]
        phase = '规划' if turn <= 3 else '执行'
        print(f'  Turn {turn} ({phase}): {names}')


if __name__ == '__main__':
    demo_loop_guard()
    demo_planning_phase()
    print('\n全部验证通过')
