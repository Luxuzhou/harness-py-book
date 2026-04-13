"""
第1章 实验数据展示
==================
展示《三大Harness实战横评》公众号文章（2026年4月6日）的真实实验结果。
数据来自笔者在同一台机器上的实际测试，不是模拟数据。

用法: python examples/ch01_experiment.py
"""

def main():
    print('='*60)
    print('  第1章实验结果（数据来源：公众号文章2026-04-06）')
    print('='*60)

    # 数据来自真实测试，详见《Claude Code vs Codex vs Claw Code》
    results = [
        {
            'agent': 'Claude Code',
            'model': 'Claude Opus 4.6',
            'outcome': '成功',
            'tests': '488 passed（含13新增）',
            'human_intervention': '0次',
            'time': '约3分钟',
            'key_behavior': '自动读CLAUDE.md → 依序改3文件 → mock方法名错误自主修复 → 全量验证',
        },
        {
            'agent': 'Codex CLI',
            'model': 'GPT-5.4',
            'outcome': '成功',
            'tests': '78 passed',
            'human_intervention': '1次（权限批量授权）',
            'time': '约7分钟',
            'key_behavior': 'rg扫文件树 → 批量授权 → 改3文件 → 沙箱环境自适应',
        },
        {
            'agent': 'Claw Code + DeepSeek',
            'model': 'DeepSeek-V3 (128K)',
            'outcome': '失败',
            'tests': '未完成',
            'human_intervention': '不适用',
            'time': '不适用',
            'key_behavior': '规划正确 → bash找不到自适应 → 读3300行文件 → 上下文145K+64K>128K溢出',
            'failure_reason': '模型注册表缺DeepSeek → 预检跳过 → 输出配额64K不合理 → 压缩未触发',
        },
    ]

    for r in results:
        status = '[OK]' if r['outcome'] == '成功' else '[FAIL]'
        print(f'\n{status} {r["agent"]} ({r["model"]})')
        print(f'  结果: {r["outcome"]}')
        print(f'  测试: {r["tests"]}')
        print(f'  人工介入: {r["human_intervention"]}')
        print(f'  耗时: {r["time"]}')
        print(f'  关键行为: {r["key_behavior"]}')
        if 'failure_reason' in r:
            print(f'  失败根因: {r["failure_reason"]}')

    print(f'\n{"="*60}')
    print('  核心结论: 三个Agent的模型能力都足以完成任务')
    print('  Claw Code失败是Harness层面的工程缺陷（模型注册表缺失）')
    print('  不是DeepSeek模型能力不够')
    print(f'{"="*60}')
    print(f'\n数据来源: 公众号文章《Claude Code vs Codex vs Claw Code》')
    print(f'测试日期: 2026年4月6日')


if __name__ == '__main__':
    main()
