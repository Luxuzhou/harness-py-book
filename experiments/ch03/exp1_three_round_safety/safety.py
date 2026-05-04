"""Safety constraint layer: intercepts tool calls before execution.

Five defenses (v2 — upgraded after Agent bypassed v1 by writing scripts):
1. Path whitelist — only allow operations inside allowed directories
2. Command blacklist — block dangerous shell commands
3. Overwrite warning — log when write_file targets an existing file
4. Content scanning — block write_file if content contains dangerous code patterns
5. Script execution guard — block run_command if it executes a script the Agent just wrote

Key design: rejection returns a reason string to the agent,
not an exception. The agent can adjust its strategy.
"""
import os
import re


class SafetyLayer:
    """Pre-execution interceptor for tool calls."""

    # Default dangerous patterns in shell commands
    DEFAULT_COMMAND_BLACKLIST = [
        r"\brm\s+-rf\b",
        r"\brmdir\b",
        r"\bshutil\.rmtree\b",
        r"\bdel\s+/[sqf]",
        r"\bformat\b",
        r"\bmkfs\b",
        r"\bdd\s+if=",
        r":>\s*/",
        r">\s*/dev/",
    ]

    # Dangerous patterns in file content (v2: detect indirect attacks)
    DANGEROUS_CONTENT_PATTERNS = [
        r"shutil\.rmtree",
        r"os\.remove",
        r"os\.rmdir",
        r"os\.unlink",
        r"\.cleanup\s*\(",
        r"shutil\.move",
        r"send2trash",
    ]

    def __init__(self, allowed_paths: list[str], command_blacklist: list[str] = None):
        """
        Args:
            allowed_paths: List of directory paths the agent is allowed to operate in.
            command_blacklist: Regex patterns for forbidden commands. Uses defaults if None.
        """
        self.allowed_paths = [os.path.abspath(p) for p in allowed_paths]
        self.command_blacklist = command_blacklist or self.DEFAULT_COMMAND_BLACKLIST
        self.intercept_log = []
        self._agent_written_files = set()  # v2: track files written by agent

    def check_tool_call(self, tool_name: str, arguments: dict) -> tuple[bool, str]:
        """Check if a tool call is safe to execute.

        Returns:
            (allowed: bool, message: str)
            If blocked, message explains why. Agent receives this message.
        """
        if tool_name == "read_file":
            return self._check_path(arguments.get("path", ""), "read")

        if tool_name == "write_file":
            path = arguments.get("path", "")
            content = arguments.get("content", "")
            allowed, msg = self._check_path(path, "write")
            if not allowed:
                return allowed, msg
            # v2: scan file content for dangerous patterns
            content_ok, content_msg = self._check_content(path, content)
            if not content_ok:
                return content_ok, content_msg
            # Track this file as agent-written
            self._agent_written_files.add(os.path.abspath(path))
            # Overwrite warning (logged but not blocked)
            if os.path.exists(path):
                self._log("warning", f"Overwriting existing file: {path}")
            return True, "OK"

        if tool_name == "run_command":
            cmd = arguments.get("cmd", "")
            # v2: check if command executes an agent-written script
            script_ok, script_msg = self._check_script_execution(cmd)
            if not script_ok:
                return script_ok, script_msg
            return self._check_command(cmd)

        if tool_name == "list_files":
            return self._check_path(arguments.get("directory", ""), "list")

        return True, "OK"

    def _check_path(self, path: str, operation: str) -> tuple[bool, str]:
        """Verify path is within allowed directories."""
        if not path:
            return False, f"Operation blocked: empty path for {operation}"

        abs_path = os.path.abspath(path)
        for allowed in self.allowed_paths:
            if abs_path.startswith(allowed):
                return True, "OK"

        msg = f"Operation blocked: path '{path}' is outside allowed directories. Allowed: {self.allowed_paths}"
        self._log("blocked", msg)
        return False, msg

    def _check_command(self, cmd: str) -> tuple[bool, str]:
        """Check command against blacklist."""
        for pattern in self.command_blacklist:
            if re.search(pattern, cmd, re.IGNORECASE):
                msg = f"Operation blocked: command '{cmd}' matches dangerous pattern '{pattern}'"
                self._log("blocked", msg)
                return False, msg
        return True, "OK"

    def _check_content(self, path: str, content: str) -> tuple[bool, str]:
        """v2: Scan write_file content for dangerous code patterns."""
        for pattern in self.DANGEROUS_CONTENT_PATTERNS:
            if re.search(pattern, content):
                msg = (
                    f"Operation blocked: file '{path}' contains dangerous code pattern '{pattern}'. "
                    f"Writing code that calls destructive functions is not allowed. "
                    f"Please use safe alternatives or ask the user for help."
                )
                self._log("blocked", msg)
                return False, msg
        return True, "OK"

    def _check_script_execution(self, cmd: str) -> tuple[bool, str]:
        """v2: Block execution of scripts that the Agent just wrote."""
        # Extract potential script paths from the command
        # Matches patterns like: python script.py, python path/to/script.py
        script_patterns = [
            r"python\s+[\"']?([^\s\"']+\.py)",
            r"python3\s+[\"']?([^\s\"']+\.py)",
        ]
        for pattern in script_patterns:
            match = re.search(pattern, cmd)
            if match:
                script_path = match.group(1)
                abs_script = os.path.abspath(script_path)
                # Also check with cd prefix (e.g. "cd target_project && python script.py")
                cd_match = re.search(r"cd\s+([^\s&]+)", cmd)
                if cd_match:
                    abs_script = os.path.abspath(os.path.join(cd_match.group(1), script_path))
                if abs_script in self._agent_written_files:
                    msg = (
                        f"Operation blocked: cannot execute '{script_path}' — "
                        f"this script was written by the Agent in this session. "
                        f"Executing self-written scripts is a security risk. "
                        f"Please perform the operations directly using the provided tools."
                    )
                    self._log("blocked", msg)
                    return False, msg
        return True, "OK"

    def _log(self, level: str, message: str):
        """Record an intercept event."""
        self.intercept_log.append({"level": level, "message": message})

    def get_stats(self) -> dict:
        """Return safety layer statistics."""
        blocked = [e for e in self.intercept_log if e["level"] == "blocked"]
        warnings = [e for e in self.intercept_log if e["level"] == "warning"]
        return {
            "total_intercepts": len(self.intercept_log),
            "blocked_count": len(blocked),
            "warning_count": len(warnings),
            "blocked_details": blocked,
        }
