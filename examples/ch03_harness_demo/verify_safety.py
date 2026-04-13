"""验证安全层是否正常工作（不消耗API）"""
import os
from safety import SafetyLayer

s = SafetyLayer(allowed_paths=[os.path.abspath("target_project")])

tests = [
    ("read_file", {"path": "target_project/calculator.py"}, "读取项目内文件"),
    ("read_file", {"path": "/etc/passwd"}, "读取系统文件"),
    ("run_command", {"cmd": "rm -rf /"}, "危险删除命令"),
    ("run_command", {"cmd": "python -m pytest"}, "正常测试命令"),
    ("write_file", {"path": "../../secret.txt", "content": "hack"}, "写入项目外文件"),
]

print("=" * 60)
print("安全层验证")
print("=" * 60)

for tool, args, desc in tests:
    allowed, msg = s.check_tool_call(tool, args)
    status = "✅ 允许" if allowed else "🚫 拦截"
    print(f"\n{desc}")
    print(f"  工具: {tool}, 参数: {args}")
    print(f"  结果: {status}")
    if not allowed:
        print(f"  原因: {msg[:80]}")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
