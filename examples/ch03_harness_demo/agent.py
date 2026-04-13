"""Core agent loop: call DeepSeek API, parse tool_use, execute, repeat.

This is the minimal agent loop without any harness layers.
It demonstrates what a "bare" coding agent looks like.
"""
import json
from openai import OpenAI
from tools import TOOL_DEFINITIONS, execute_tool


class AgentLoop:
    """Minimal ReAct-style agent loop using DeepSeek API."""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com", model: str = "deepseek-chat"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.metrics = {
            "total_steps": 0,
            "tokens_used": {"prompt": 0, "completion": 0},
            "tool_calls": [],
            "errors": 0,
        }

    def run(
        self,
        task: str,
        system_prompt: str = "You are a coding assistant. Use the provided tools to complete the task.",
        tool_defs: list = None,
        tool_executor=None,
        max_steps: int = 15,
    ) -> dict:
        """Run the agent loop until task completion or max steps.

        Args:
            task: The user's task description.
            system_prompt: System prompt (bare agent uses a minimal one).
            tool_defs: Tool definitions for function calling. Defaults to TOOL_DEFINITIONS.
            tool_executor: Function to execute tools. Defaults to execute_tool.
            max_steps: Maximum number of loop iterations.

        Returns:
            dict with keys: final_response, messages, metrics
        """
        if tool_defs is None:
            tool_defs = TOOL_DEFINITIONS
        if tool_executor is None:
            tool_executor = execute_tool

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        for step in range(max_steps):
            self.metrics["total_steps"] = step + 1

            # Call DeepSeek API
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tool_defs,
                    tool_choice="auto",
                )
            except Exception as e:
                self.metrics["errors"] += 1
                return {
                    "final_response": f"API error: {e}",
                    "messages": messages,
                    "metrics": self.metrics,
                }

            # Track token usage
            if response.usage:
                self.metrics["tokens_used"]["prompt"] += response.usage.prompt_tokens
                self.metrics["tokens_used"]["completion"] += response.usage.completion_tokens

            choice = response.choices[0]
            assistant_msg = choice.message

            # If no tool calls, the agent is done
            if not assistant_msg.tool_calls:
                messages.append({"role": "assistant", "content": assistant_msg.content or ""})
                return {
                    "final_response": assistant_msg.content or "",
                    "messages": messages,
                    "metrics": self.metrics,
                }

            # Process tool calls
            messages.append({
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in assistant_msg.tool_calls
                ],
            })

            for tool_call in assistant_msg.tool_calls:
                func_name = tool_call.function.name
                try:
                    func_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    func_args = {}

                self.metrics["tool_calls"].append({"name": func_name, "args": func_args})

                # Execute tool
                result = tool_executor(func_name, func_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                })

        # Max steps reached
        return {
            "final_response": "(max steps reached)",
            "messages": messages,
            "metrics": self.metrics,
        }
