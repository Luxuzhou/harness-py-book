"""
Hook系统
========
对标OpenHarness的hooks/executor + Claude Code的PRE_TOOL_USE/POST_TOOL_USE。
为Case 2（医疗合规）提供关键支撑。

Hook是Harness约束层的运行时延伸：
CLAUDE.md编码静态规则，Hook执行动态检查。
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import AgentConfig, HookConfig


@dataclass
class HookResult:
    """Hook执行结果。"""
    allowed: bool = True
    reason: str = ''
    filtered_result: str = ''
    warnings: list[str] | None = None


class HookExecutor:
    """
    Hook执行器。

    在工具执行前后调用注册的hook函数：
    - pre_tool: (tool_name, tool_args, config_dict) → (allow, reason)
    - post_tool: (tool_name, tool_args, result, config_dict) → (filtered_result, warnings)
    """

    def __init__(self, hook_config: HookConfig | None = None):
        self.hook_config = hook_config or HookConfig()

    def pre_tool(self, tool_name: str, tool_args: dict, config: AgentConfig) -> HookResult:
        """工具执行前检查。"""
        if not self.hook_config.pre_tool:
            return HookResult(allowed=True)

        try:
            config_dict = {
                'cwd': str(config.cwd),
                'allow_write': config.allow_write,
                'allow_shell': config.allow_shell,
                'role': config.role,
            }
            allowed, reason = self.hook_config.pre_tool(tool_name, tool_args, config_dict)
            return HookResult(allowed=allowed, reason=reason)
        except Exception as e:
            return HookResult(allowed=False, reason=f'Hook异常: {e}')

    def post_tool(self, tool_name: str, tool_args: dict, result: str, config: AgentConfig) -> HookResult:
        """工具执行后过滤。"""
        if not self.hook_config.post_tool:
            return HookResult(allowed=True, filtered_result=result)

        try:
            config_dict = {'cwd': str(config.cwd), 'role': config.role}
            filtered, warnings = self.hook_config.post_tool(tool_name, tool_args, result, config_dict)
            return HookResult(
                allowed=True,
                filtered_result=filtered,
                warnings=warnings or [],
            )
        except Exception as e:
            return HookResult(allowed=True, filtered_result=result, warnings=[f'Post-hook异常: {e}'])
