"""
第2章：Harness设计检查清单——自动扫描项目的Harness完成度
======================================================
不需要API key。扫描指定目录，评估六层架构的覆盖度。
用法: python standalone/ch02_checklist.py [项目目录]
"""
import sys
from pathlib import Path


def check_layer(name: str, checks: list[tuple[str, bool]]) -> tuple[int, int]:
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    icon = '✅' if passed == total else '⚠️' if passed > 0 else '❌'
    print(f'\n  {icon} {name}（{passed}/{total}）')
    for desc, ok in checks:
        print(f'    {"✓" if ok else "✗"} {desc}')
    return passed, total


def scan_project(cwd: Path):
    print(f'\n扫描目录: {cwd}\n')
    print('=' * 50)
    print('  Harness Engineering 六层架构检查清单')
    print('=' * 50)

    total_passed, total_checks = 0, 0

    # ① 约束层
    p, t = check_layer('① 约束层（Constraints）', [
        ('有CLAUDE.md或AGENTS.md', (cwd / 'CLAUDE.md').exists() or (cwd / 'AGENTS.md').exists()),
        ('有.claude/rules/目录', (cwd / '.claude' / 'rules').is_dir()),
        ('无.env文件暴露在根目录', not (cwd / '.env').exists() or (
            (cwd / '.gitignore').exists() and
            '.env' in (cwd / '.gitignore').read_text(encoding='utf-8', errors='replace')
        )),
    ])
    total_passed += p; total_checks += t

    # ② 工具层
    p, t = check_layer('② 工具层（Tools）', [
        ('有可执行的测试命令', (cwd / 'tests').is_dir() or (cwd / 'test').is_dir()),
        ('有package.json/pyproject.toml/Makefile', any((cwd / f).exists() for f in ['package.json', 'pyproject.toml', 'Makefile'])),
    ])
    total_passed += p; total_checks += t

    # ③ 上下文层
    claude_md = (cwd / 'CLAUDE.md')
    claude_content = claude_md.read_text(encoding='utf-8') if claude_md.exists() else ''
    p, t = check_layer('③ 上下文层（Context）', [
        ('CLAUDE.md存在', claude_md.exists()),
        ('CLAUDE.md不超过200行', claude_md.exists() and len(claude_content.splitlines()) <= 200),
        ('有docs/或README.md', (cwd / 'docs').is_dir() or (cwd / 'README.md').exists()),
    ])
    total_passed += p; total_checks += t

    # ④ 记忆层
    memory_dir = Path.home() / '.claude' / 'projects'
    has_memory = any(memory_dir.glob('*/memory/MEMORY.md')) if memory_dir.exists() else False
    p, t = check_layer('④ 记忆层（Memory）', [
        ('有Auto Memory目录', has_memory),
        ('有.gitignore', (cwd / '.gitignore').exists()),
        ('有CLAUDE.md中的Compact Instructions', 'Compact Instructions' in claude_content),
    ])
    total_passed += p; total_checks += t

    # ⑤ 验证层
    p, t = check_layer('⑤ 验证层（Verification）', [
        ('有测试文件', any(cwd.rglob('test_*.py')) or any(cwd.rglob('*.test.js'))),
        ('有CI配置', any((cwd / d).exists() for d in ['.github/workflows', '.gitlab-ci.yml', 'Jenkinsfile'])),
    ])
    total_passed += p; total_checks += t

    # ⑥ 编排层
    p, t = check_layer('⑥ 编排层（Orchestration）', [
        ('有多文件项目结构', len(list(cwd.glob('**/*.py')))>3 or len(list(cwd.glob('**/*.js')))>3),
    ])
    total_passed += p; total_checks += t

    # 总评
    pct = total_passed / total_checks * 100 if total_checks > 0 else 0
    print(f'\n{"=" * 50}')
    print(f'  总评: {total_passed}/{total_checks} ({pct:.0f}%)')
    if pct >= 80:
        print('  Harness就绪度: 高')
    elif pct >= 50:
        print('  Harness就绪度: 中（建议补充CLAUDE.md和测试）')
    else:
        print('  Harness就绪度: 低（建议先写CLAUDE.md，再加测试）')


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    scan_project(target)
