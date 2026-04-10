"""
第2章 六层检查清单
==================
扫描项目目录，逐层检查Harness成熟度。纯文件系统操作，无需API。

用法: python examples/ch02_checklist.py [项目目录]
"""

import sys
from pathlib import Path


def scan_layer(name: str, checks: list[tuple[str, bool]]) -> int:
    """扫描一层，返回通过数。"""
    passed = 0
    print(f'\n  {name}')
    for desc, ok in checks:
        status = 'PASS' if ok else 'FAIL'
        print(f'    {"[v]" if ok else "[x]"} {desc}')
        if ok:
            passed += 1
    return passed


def main(cwd: Path):
    print(f'Harness六层检查清单: {cwd}')
    print('='*50)

    total, passed = 0, 0

    # 约束层
    gitignore = cwd / '.gitignore'
    env_safe = not (cwd / '.env').exists() or (
        gitignore.exists() and '.env' in gitignore.read_text(encoding='utf-8', errors='replace')
    )
    checks = [
        ('CLAUDE.md或AGENTS.md存在', (cwd / 'CLAUDE.md').exists() or (cwd / 'AGENTS.md').exists()),
        ('.env不暴露（无.env或已在.gitignore中）', env_safe),
    ]
    p = scan_layer('① 约束层', checks)
    total += len(checks); passed += p

    # 工具层
    checks = [
        ('有可执行的构建/测试命令', any((cwd / f).exists() for f in ['Makefile', 'package.json', 'pyproject.toml', 'setup.py'])),
    ]
    p = scan_layer('② 工具层', checks)
    total += len(checks); passed += p

    # 上下文层
    checks = [
        ('有README或文档目录', (cwd / 'README.md').exists() or (cwd / 'docs').is_dir()),
    ]
    p = scan_layer('③ 上下文层', checks)
    total += len(checks); passed += p

    # 记忆层
    checks = [
        ('有Git版本控制', (cwd / '.git').is_dir()),
    ]
    p = scan_layer('④ 记忆层', checks)
    total += len(checks); passed += p

    # 验证层
    has_tests = any(cwd.rglob('test_*.py')) or any(cwd.rglob('*.test.js'))
    checks = [
        ('有测试文件', has_tests),
    ]
    p = scan_layer('⑤ 验证层', checks)
    total += len(checks); passed += p

    # 编排层
    has_ci = any((cwd / d).exists() for d in ['.github/workflows', '.gitlab-ci.yml', 'Jenkinsfile'])
    checks = [
        ('有CI配置', has_ci),
    ]
    p = scan_layer('⑥ 编排层', checks)
    total += len(checks); passed += p

    print(f'\n{"="*50}')
    print(f'结果: {passed}/{total} 通过 ({passed/total*100:.0f}%)')


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    main(target)
