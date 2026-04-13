"""Harness assembler: composes layers and provides run() interface.

Supports 5 levels:
- Level 0: bare agent (agent + tools only)
- Level 1: + safety layer
- Level 2: + context layer
- Level 3: + recovery layer
- Level 4: full harness (all layers + config)
"""
from agent import AgentLoop
from tools import TOOL_DEFINITIONS, execute_tool
from safety import SafetyLayer
from context import ContextLayer
from recovery import RecoveryLayer


class Harness:
    """Assembles harness layers and runs the agent."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        project_dir: str = "target_project",
        level: int = 4,
        project_rules: dict = None,
        allowed_paths: list[str] = None,
        command_blacklist: list[str] = None,
        max_steps: int = 15,
    ):
        self.level = level
        self.max_steps = max_steps
        self.project_dir = project_dir

        # Core: always present
        self.agent = AgentLoop(api_key=api_key, base_url=base_url, model=model)

        # Layer 1: Safety (level >= 1)
        self.safety = None
        if level >= 1:
            paths = allowed_paths or [project_dir]
            self.safety = SafetyLayer(allowed_paths=paths, command_blacklist=command_blacklist)

        # Layer 2: Context (level >= 2)
        self.context = None
        if level >= 2:
            self.context = ContextLayer(
                project_dir=project_dir,
                project_rules=project_rules,
            )

        # Layer 3: Recovery (level >= 3)
        self.recovery = None
        if level >= 3:
            self.recovery = RecoveryLayer()

    def run(self, task: str) -> dict:
        """Run the agent with the configured harness level.

        Returns:
            dict with: final_response, messages, metrics, safety_stats, recovery_stats
        """
        # Build system prompt
        if self.context:
            system_prompt = self.context.build_system_prompt()
        else:
            system_prompt = "You are a coding assistant. Use the provided tools to complete the task."

        # Build tool executor with safety + recovery wrapping
        tool_executor = self._build_executor()

        # Run agent loop
        result = self.agent.run(
            task=task,
            system_prompt=system_prompt,
            tool_defs=TOOL_DEFINITIONS,
            tool_executor=tool_executor,
            max_steps=self.max_steps,
        )

        # Attach layer stats
        result["harness_level"] = self.level
        result["safety_stats"] = self.safety.get_stats() if self.safety else None
        result["recovery_stats"] = self.recovery.get_stats() if self.recovery else None

        return result

    def _build_executor(self):
        """Build the tool executor chain based on harness level."""

        def executor(tool_name: str, arguments: dict) -> str:
            # Layer 1: Safety check
            if self.safety:
                allowed, message = self.safety.check_tool_call(tool_name, arguments)
                if not allowed:
                    return message  # Return rejection reason to agent

            # Layer 3: Recovery-wrapped execution
            if self.recovery:
                return self.recovery.execute_with_recovery(
                    tool_name, arguments, base_executor=execute_tool
                )

            # Bare execution
            return execute_tool(tool_name, arguments)

        return executor
