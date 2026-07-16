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
        'src/main/java/com/example/cp/controller/',
        'src/test/java/com/example/cp/service/',
        'REFACTOR_REPORT.md',
    )
    # Controller 层允许有限修改：重构拆分后需要更新依赖注入关系。
    # 对外 API 契约由 verify.py 的路由基线检查兜底，不在 Hook 中一刀切冻结。
    FROZEN_PREFIXES = (
        'src/main/java/com/example/cp/dto/',
        'src/main/java/com/example/cp/mapper/',
        'src/main/java/com/example/cp/model/',
        'src/main/java/com/example/cp/enums/',
        'pom.xml',
    )
    FROZEN_CASE_FILES = ('verify.py', 'TASK.md', 'CLAUDE.md')
    BASH_WRITE_MARKERS = (
        '>', '>>', 'sed -i', 'perl -pi', 'python -c', 'python - <<',
        'set-content', 'add-content', 'out-file',
        'cp ', 'copy ', 'mv ', 'move ', 'ren ', 'rename ', 'tee ',
        'del ', 'erase ', 'remove-item', 'set-itemproperty',
    )

    def pre_tool(tool_name: str, tool_args: dict, config: dict) -> tuple[bool, str]:
        if tool_name == 'bash':
            command = str(tool_args.get('command') or '')
            norm_cmd = command.replace('\\', '/').lower()
            touches_case_file = any(name.lower() in norm_cmd for name in FROZEN_CASE_FILES)
            writes = any(marker in norm_cmd for marker in BASH_WRITE_MARKERS)
            if touches_case_file and writes:
                return False, 'Hook 拦截：验收脚本与任务说明只允许读取/执行，不允许通过 bash 改写'

        if tool_name in {'write_file', 'edit_file'}:
            path = tool_args.get('path') or tool_args.get('file_path') or ''
            norm = str(path).replace('\\', '/')
            if any(norm.endswith(name) or f'/{name}' in norm for name in FROZEN_CASE_FILES):
                return False, f'Hook 拦截："{path}" 是验收/任务文件，不允许改写'
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
            max_iterations=120,
            planning_turns=5,
            allow_write=True,
            allow_shell=True,
            sandbox_mode='bypass',
            network_isolated=True,
            allowed_paths=[str(target_dir)],
            read_only_paths=[str(CASE_DIR / 'verify.py'), str(CASE_DIR / 'TASK.md'), str(CASE_DIR / 'CLAUDE.md')],
            filesystem_roots=['.', str(CASE_DIR), str(REPO_ROOT)],  # 允许访问项目根
            hooks=hooks,
            system_prompt_append=claude_md,
            acceptance_commands=['python -B ../verify.py'],
            acceptance_timeout=300,
            reset_plan_state=True,
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
