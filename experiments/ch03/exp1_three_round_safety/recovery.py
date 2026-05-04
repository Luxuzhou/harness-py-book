"""Fault recovery layer: retry, circuit breaker, safe-mode fallback.

Three mechanisms:
1. Retry: up to 2 retries with exponential backoff on tool execution errors
2. Circuit breaker: stop after max_steps or timeout
3. Safe mode: after 3 consecutive failures, switch to read-only tools
"""
import time
from tools import execute_tool


class RecoveryLayer:
    """Wraps tool execution with fault tolerance."""

    def __init__(self, max_retries: int = 2, max_consecutive_failures: int = 3):
        self.max_retries = max_retries
        self.max_consecutive_failures = max_consecutive_failures
        self.consecutive_failures = 0
        self.safe_mode = False
        self.recovery_log = []

    # Tools allowed in safe mode (read-only)
    SAFE_MODE_TOOLS = {"read_file", "list_files"}

    def execute_with_recovery(self, tool_name: str, arguments: dict, base_executor=None) -> str:
        """Execute a tool call with retry and safe-mode logic.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments dict.
            base_executor: Underlying executor function. Defaults to execute_tool.

        Returns:
            Tool execution result string.
        """
        if base_executor is None:
            base_executor = execute_tool

        # Safe mode: block write operations
        if self.safe_mode and tool_name not in self.SAFE_MODE_TOOLS:
            msg = (
                f"SAFE MODE ACTIVE: Tool '{tool_name}' is blocked. "
                f"Only {self.SAFE_MODE_TOOLS} are allowed. "
                "The agent has entered safe mode due to consecutive failures. "
                "Please report the current situation to the user."
            )
            self._log("safe_mode_block", tool_name, msg)
            return msg

        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                result = base_executor(tool_name, arguments)

                # Check if the result indicates an error
                if result.startswith("Error"):
                    raise RuntimeError(result)

                # Success: reset failure counter
                self.consecutive_failures = 0
                return result

            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    wait = 2 ** attempt  # 1s, 2s
                    self._log("retry", tool_name, f"Attempt {attempt + 1} failed: {last_error}. Retrying in {wait}s...")
                    time.sleep(wait)

        # All retries exhausted
        self.consecutive_failures += 1
        self._log("failure", tool_name, f"All {self.max_retries + 1} attempts failed: {last_error}")

        # Check if we should enter safe mode
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.safe_mode = True
            self._log("safe_mode_enter", tool_name, f"Entered safe mode after {self.consecutive_failures} consecutive failures")

        return f"Error (after {self.max_retries + 1} attempts): {last_error}"

    def _log(self, event: str, tool_name: str, message: str):
        """Record a recovery event."""
        self.recovery_log.append({
            "event": event,
            "tool": tool_name,
            "message": message,
            "timestamp": time.time(),
        })

    def get_stats(self) -> dict:
        """Return recovery layer statistics."""
        retries = [e for e in self.recovery_log if e["event"] == "retry"]
        failures = [e for e in self.recovery_log if e["event"] == "failure"]
        return {
            "total_retries": len(retries),
            "total_failures": len(failures),
            "safe_mode_entered": self.safe_mode,
            "consecutive_failures": self.consecutive_failures,
            "log": self.recovery_log,
        }
