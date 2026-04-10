"""
医疗数据合规Hooks
================
实现pre_tool和post_tool钩子，用于：
1. 文件访问审计（记录每次数据读取）
2. 输出过滤（拦截包含患者ID的输出）
3. 网络隔离（拦截网络命令）
"""

import re
import json
from datetime import datetime, timezone
from pathlib import Path

# 患者ID模式
PAT_ID_PATTERN = re.compile(r'PAT-\d{5}')

# 禁止的网络命令
NETWORK_COMMANDS = {'curl', 'wget', 'ping', 'ssh', 'nc', 'netcat', 'telnet', 'ftp', 'scp'}

# 禁止的Python网络模块
NETWORK_MODULES = {'requests', 'urllib', 'socket', 'http.client', 'httpx', 'aiohttp'}


def pre_tool_hook(tool_name: str, tool_args: dict, config: dict) -> tuple[bool, str]:
    """
    工具执行前的合规检查。

    返回 (allow, reason)：
    - (True, '') 允许执行
    - (False, reason) 拒绝执行，reason说明原因
    """
    case_dir = Path(config.get('cwd', '.'))

    # 规则1：bash命令网络隔离
    if tool_name == 'bash':
        cmd = tool_args.get('command', tool_args.get('cmd', ''))
        first_word = cmd.strip().split()[0] if cmd.strip() else ''

        if first_word in NETWORK_COMMANDS:
            return False, f'合规拦截: 禁止执行网络命令 "{first_word}"'

        # 检查Python脚本中的网络模块
        if 'python' in first_word:
            for mod in NETWORK_MODULES:
                if f'import {mod}' in cmd or f'from {mod}' in cmd:
                    return False, f'合规拦截: 禁止使用网络模块 "{mod}"'

    # 规则2：文件读取路径限制
    if tool_name == 'read_file':
        path = tool_args.get('path', '')
        resolved = (case_dir / path).resolve()
        allowed_roots = [
            case_dir.resolve(),
            (case_dir / 'sample_data').resolve(),
        ]
        if not any(str(resolved).startswith(str(root)) for root in allowed_roots):
            return False, f'合规拦截: 不允许读取 {path}（超出允许范围）'

    # 规则3：文件写入路径限制
    if tool_name in ('write_file', 'edit_file'):
        path = tool_args.get('path', '')
        resolved = (case_dir / path).resolve()
        if not str(resolved).startswith(str(case_dir.resolve())):
            return False, f'合规拦截: 不允许写入 {path}（超出案例目录）'

        # 不允许覆盖原始数据
        if 'sample_data' in str(resolved):
            return False, f'合规拦截: 不允许修改原始数据文件'

    return True, ''


def post_tool_hook(tool_name: str, tool_args: dict, result: str, config: dict) -> tuple[str, list[str]]:
    """
    工具执行后的合规过滤。

    返回 (filtered_result, warnings)：
    - filtered_result: 过滤后的结果（患者ID被替换）
    - warnings: 合规警告列表
    """
    warnings = []

    # 规则4：过滤输出中的患者ID
    if PAT_ID_PATTERN.search(result):
        count = len(PAT_ID_PATTERN.findall(result))
        result = PAT_ID_PATTERN.sub('[REDACTED]', result)
        warnings.append(f'合规过滤: 已屏蔽 {count} 个患者ID')

    # 规则5：审计记录
    case_dir = Path(config.get('cwd', '.'))
    log_path = case_dir / 'compliance_log.jsonl'

    log_entry = {
        'time': datetime.now(timezone.utc).isoformat(),
        'tool': tool_name,
        'action': _classify_action(tool_name),
        'target': _extract_target(tool_args),
        'warnings': warnings,
    }

    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except OSError:
        warnings.append('警告: 无法写入合规日志')

    return result, warnings


def _classify_action(tool_name: str) -> str:
    """分类操作类型。"""
    if tool_name in ('read_file', 'grep_search', 'glob_search'):
        return 'read'
    if tool_name in ('write_file', 'edit_file'):
        return 'write'
    if tool_name == 'bash':
        return 'execute'
    return 'other'


def _extract_target(tool_args: dict) -> str:
    """提取操作目标。"""
    return tool_args.get('path', tool_args.get('pattern', tool_args.get('command', '')[:80]))


def validate_report(report_path: str) -> tuple[bool, list[str]]:
    """
    验证最终报告的合规性。

    返回 (compliant, issues)
    """
    issues = []
    try:
        content = Path(report_path).read_text(encoding='utf-8')
    except FileNotFoundError:
        return False, ['报告文件不存在']

    # 检查患者ID泄露
    pat_ids = PAT_ID_PATTERN.findall(content)
    if pat_ids:
        issues.append(f'报告中包含 {len(pat_ids)} 个患者ID: {pat_ids[:3]}...')

    # 检查是否包含聚合数据
    has_stats = any(kw in content for kw in ['均值', '中位数', '标准差', '异常率', 'mean', 'median'])
    if not has_stats:
        issues.append('报告缺少统计聚合数据')

    return len(issues) == 0, issues
