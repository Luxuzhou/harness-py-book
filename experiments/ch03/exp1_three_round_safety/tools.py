"""Tool definitions and raw executors for the coding agent.

Provides 4 tools in OpenAI-compatible function calling format:
- read_file: Read file contents
- write_file: Write/overwrite a file
- run_command: Execute a shell command
- list_files: List directory contents
"""
import os
import subprocess


# --- Tool Definitions (OpenAI function calling format) ---

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to read",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to write to",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {
                        "type": "string",
                        "description": "The shell command to execute",
                    }
                },
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files and directories at the given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "The directory path to list",
                    }
                },
                "required": ["directory"],
            },
        },
    },
]


# --- Raw Executors ---


def execute_read_file(path: str) -> str:
    """Read file contents. Returns content or error message."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def execute_write_file(path: str, content: str) -> str:
    """Write content to file. Returns success or error message."""
    try:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def execute_run_command(cmd: str) -> str:
    """Execute shell command. Returns stdout+stderr or error."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\nReturn code: {result.returncode}"
        return output if output.strip() else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing command: {e}"


def execute_list_files(directory: str) -> str:
    """List directory contents. Returns file list or error."""
    try:
        if not os.path.exists(directory):
            return f"Error: Directory not found: {directory}"
        entries = os.listdir(directory)
        if not entries:
            return "(empty directory)"
        return "\n".join(sorted(entries))
    except Exception as e:
        return f"Error listing directory: {e}"


# --- Dispatcher ---

TOOL_EXECUTORS = {
    "read_file": lambda args: execute_read_file(args["path"]),
    "write_file": lambda args: execute_write_file(args["path"], args["content"]),
    "run_command": lambda args: execute_run_command(args["cmd"]),
    "list_files": lambda args: execute_list_files(args["directory"]),
}


def execute_tool(name: str, arguments: dict) -> str:
    """Dispatch a tool call to its executor."""
    executor = TOOL_EXECUTORS.get(name)
    if not executor:
        return f"Error: Unknown tool: {name}"
    return executor(arguments)
