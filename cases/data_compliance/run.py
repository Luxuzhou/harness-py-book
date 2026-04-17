"""
数据合规改造案例 — 单 Agent 三层防御执行入口。

用法：
    python cases/data_compliance/run.py

依赖 .env 中的 OPENAI_API_KEY 或 HARNESS_API_KEY。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

CASE_DIR = Path(__file__).parent
REPO_ROOT = CASE_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT))

# 加载 .env
env_file = REPO_ROOT / '.env'
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())


def _build_hook_config():
    """构造合规 Hook：pre_tool 拦截危险模式，post_tool 扫描 PII 泄露。"""
    from harness_py_pro.config import HookConfig

    DANGEROUS_SQL_PATTERNS = [
        'execute(f"',
        "execute(f'",
        '" + ',
        "' + ",
        '"%s" %',
    ]
    PII_KEYWORDS = ['id_card', '身份证号', 'phone']

    def pre_tool(tool_name: str, tool_args: dict) -> tuple[bool, str]:
        if tool_name in {'write_file', 'edit_file'}:
            content = tool_args.get('content') or tool_args.get('new_str') or ''
            for pat in DANGEROUS_SQL_PATTERNS:
                if pat in content and ('SELECT' in content or 'INSERT' in content
                                        or 'UPDATE' in content or 'DELETE' in content):
                    return False, f'Hook 拦截：检测到 SQL 字符串拼接模式 "{pat}"，必须使用参数化'
        if tool_name == 'bash':
            cmd = tool_args.get('command', '')
            if any(host in cmd for host in ('curl http', 'wget http')):
                return False, 'Hook 拦截：合规案例禁止外网请求'
        return True, ''

    def post_tool(tool_name: str, tool_args: dict, result: str) -> tuple[bool, str, list]:
        warnings: list = []
        if tool_name in {'read_file', 'bash'} and isinstance(result, str):
            for kw in PII_KEYWORDS:
                if kw in result and '***' not in result:
                    warnings.append(f'post_tool 警告：响应中出现未脱敏的 {kw} 字段')
        return True, result, warnings

    return HookConfig(pre_tool=pre_tool, post_tool=post_tool)


def main():
    from harness_py_pro import run, ModelConfig, AgentConfig

    target_dir = CASE_DIR / 'target_service'
    task = (CASE_DIR / 'TASK.md').read_text(encoding='utf-8')
    claude_md = (CASE_DIR / 'CLAUDE.md').read_text(encoding='utf-8')

    hooks = _build_hook_config()

    # 沙箱白名单：只允许在 target_service 内读写
    allowed_paths = [
        str(target_dir),
    ]

    result = run(
        task,
        model_config=ModelConfig.from_env(),
        agent_config=AgentConfig(
            cwd=target_dir,
            max_iterations=40,
            planning_turns=2,
            allow_write=True,
            allow_shell=True,
            network_isolated=True,
            allowed_paths=allowed_paths,
            hooks=hooks,
            system_prompt_append=claude_md,
        ),
    )

    print('\n' + '=' * 60)
    print('[run] 改造完成。turns={}, tool_calls={}, tokens={}, stop_reason={}'.format(
        result.turns, result.tool_calls, result.total_tokens, result.stop_reason,
    ))
    print('=' * 60)
    return result


if __name__ == '__main__':
    main()
