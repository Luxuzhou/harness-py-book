"""
Hook函数单元验证（不消耗API）。
验证 pre_tool_hook 和 post_tool_hook 的拦截/脱敏逻辑。
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 直接从实验脚本导入 Hook 函数
sys.path.insert(0, '.')
from run_hooks_experiment import pre_tool_hook, post_tool_hook

print('=' * 50)
print('  Hook 函数单元验证')
print('=' * 50)

# ---- PreToolUse 测试 ----
print('\n--- PreToolUse Hook 测试 ---')

tests_pre = [
    ('读取 .env', 'read_file', {'path': 'sample_data/.env'}, False),
    ('读取 .pem', 'read_file', {'path': 'certs/server.pem'}, False),
    ('读取 CSV', 'read_file', {'path': 'sample_data/patients_demo.csv'}, True),
    ('rm -rf', 'bash', {'command': 'rm -rf /tmp/data'}, False),
    ('DROP TABLE', 'bash', {'command': 'psql -c "DROP TABLE patients"'}, False),
    ('git push --force', 'bash', {'command': 'git push --force origin main'}, False),
    ('pytest', 'bash', {'command': 'pytest tests/'}, True),
    ('写入含身份证号', 'write_file', {'content': 'patient = "130191419371218041X"'}, False),
    ('写入普通代码', 'write_file', {'content': 'print("hello")'}, True),
]

passed = 0
for desc, tool, args, expected in tests_pre:
    allowed, reason = pre_tool_hook(tool, args, {})
    status = 'PASS' if allowed == expected else 'FAIL'
    if status == 'PASS':
        passed += 1
    icon = '+' if allowed else 'X'
    print(f'  [{status}] {desc}: [{icon}] {reason or "放行"}')

print(f'\nPreToolUse: {passed}/{len(tests_pre)} passed')

# ---- PostToolUse 测试 ----
print('\n--- PostToolUse Hook 测试 ---')

sample_output = (
    'patient_id,name,id_card,phone,gender,age,department,diagnosis\n'
    'P100000,赵文明,130191419371218041X,13812345678,male,87,急诊科,2型糖尿病\n'
    'P100001,郝海天,360110920060323193X,15923456789,male,18,老年科,慢性支气管炎\n'
    'P100002,马琳,430043019821215480X,18634567890,female,42,新生儿科,带状疱疹\n'
)

filtered, warnings = post_tool_hook('read_file', {}, sample_output, {})

print(f'  原始输出包含身份证号: {"130191419371218041X" in sample_output}')
print(f'  过滤后包含身份证号: {"130191419371218041X" in filtered}')
print(f'  警告: {warnings}')
print(f'\n  脱敏效果对比:')
print(f'  原始: 130191419371218041X → 脱敏: ', end='')

import re
pattern = re.compile(r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]')
first_id = pattern.search(filtered)
print(first_id.group() if first_id else '(已完全脱敏)')

print(f'  原始: 13812345678 → 脱敏: ', end='')
phone_pattern = re.compile(r'1[3-9]\d[\d*]{4,}\d{4}')
first_phone = phone_pattern.search(filtered)
print(first_phone.group() if first_phone else '(已完全脱敏)')

# 显示完整脱敏结果
print(f'\n  脱敏后的完整输出:')
for line in filtered.strip().split('\n'):
    print(f'    {line}')

post_pass = (
    '130191419371218041X' not in filtered
    and '13812345678' not in filtered
    and len(warnings) == 2
)
print(f'\nPostToolUse: {"PASS" if post_pass else "FAIL"}')

# ---- 总结 ----
total = passed + (1 if post_pass else 0)
total_tests = len(tests_pre) + 1
print(f'\n{"=" * 50}')
print(f'  总计: {total}/{total_tests} passed')
print(f'{"=" * 50}')
