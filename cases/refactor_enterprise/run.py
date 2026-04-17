"""
遗留系统重构案例 — Java 企业项目的 God Class 拆解。

用法：
    python cases/refactor_enterprise/run.py

依赖 .env 中的 OPENAI_API_KEY 或 HARNESS_API_KEY。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

CASE_DIR = Path(__file__).parent
REPO_ROOT = CASE_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT))

env_file = REPO_ROOT / '.env'
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())


def _build_hook_config():
    """Hook：限制写权限只在 service/ 和 src/test/ 子树；禁止改 Controller 签名。"""
    from harness_py_pro.config import HookConfig

    WRITABLE_PREFIXES = (
        'src/main/java/com/example/cp/service/',
        'src/test/java/com/example/cp/service/',
        'REFACTOR_REPORT.md',
    )
    # Controller 层允许读但禁止写
    FROZEN_PREFIXES = (
        'src/main/java/com/example/cp/controller/',
        'src/main/java/com/example/cp/dto/',
        'src/main/java/com/example/cp/mapper/',
        'src/main/java/com/example/cp/model/',
        'src/main/java/com/example/cp/enums/',
        'pom.xml',
    )

    def pre_tool(tool_name: str, tool_args: dict) -> tuple[bool, str]:
        if tool_name in {'write_file', 'edit_file'}:
            path = tool_args.get('path') or tool_args.get('file_path') or ''
            norm = str(path).replace('\\', '/')
            if any(norm.endswith(p) or f'/{p}' in norm for p in FROZEN_PREFIXES):
                return False, f'Hook 拦截：路径 "{path}" 在冻结目录，重构不得改写对外契约'
            # 至少命中一个可写前缀
            if not any(p in norm for p in WRITABLE_PREFIXES):
                return False, f'Hook 拦截：路径 "{path}" 不在重构范围（service/ 或 test/）'
        return True, ''

    return HookConfig(pre_tool=pre_tool)


def main():
    from harness_py_pro import run, ModelConfig, AgentConfig

    target_dir = CASE_DIR / 'target_project'
    task = (CASE_DIR / 'TASK.md').read_text(encoding='utf-8')
    claude_md = (CASE_DIR / 'CLAUDE.md').read_text(encoding='utf-8')
    hooks = _build_hook_config()

    result = run(
        task,
        model_config=ModelConfig.from_env(),
        agent_config=AgentConfig(
            cwd=target_dir,
            max_iterations=50,
            planning_turns=3,
            allow_write=True,
            allow_shell=True,
            network_isolated=True,
            allowed_paths=[str(target_dir)],
            hooks=hooks,
            system_prompt_append=claude_md,
        ),
    )

    print('\n' + '=' * 60)
    print('[run] 重构完成。turns={}, tool_calls={}, tokens={}, stop_reason={}'.format(
        result.turns, result.tool_calls, result.total_tokens, result.stop_reason,
    ))
    print('=' * 60)
    return result


if __name__ == '__main__':
    main()
