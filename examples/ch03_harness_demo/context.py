"""Context assembly layer: builds rich system prompts from project state.

Assembles:
- base_prompt: basic role definition
- project_rules: coding standards from config
- file_summary: target project file inventory
- conversation_history: with compression when over token budget
"""
import os


class ContextLayer:
    """Assembles system prompts with project context."""

    BASE_PROMPT = "You are a coding assistant. Use the provided tools to complete the task."

    def __init__(self, project_dir: str, project_rules: dict = None, max_history_tokens: int = 4000):
        """
        Args:
            project_dir: Path to the target project directory.
            project_rules: Dict of coding rules from config.yaml.
            max_history_tokens: Approximate token budget for conversation history.
        """
        self.project_dir = project_dir
        self.project_rules = project_rules or {}
        self.max_history_tokens = max_history_tokens

    def build_system_prompt(self) -> str:
        """Assemble the full system prompt with all context layers."""
        parts = [self.BASE_PROMPT]

        # Project rules
        if self.project_rules:
            rules_text = "\n## Project Rules\nFollow these rules strictly:\n"
            for key, value in self.project_rules.items():
                rules_text += f"- {key}: {value}\n"
            parts.append(rules_text)

        # File summary
        file_summary = self._build_file_summary()
        if file_summary:
            parts.append(f"\n## Project Files\n{file_summary}")

        return "\n".join(parts)

    def _build_file_summary(self) -> str:
        """Scan target project and build a file inventory with previews."""
        if not os.path.exists(self.project_dir):
            return ""

        lines = []
        for root, dirs, files in os.walk(self.project_dir):
            # Skip __pycache__ and hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
            for fname in sorted(files):
                if fname.startswith(".") or fname.endswith(".pyc"):
                    continue
                rel_path = os.path.relpath(os.path.join(root, fname), self.project_dir)
                # Read first few lines as preview
                full_path = os.path.join(root, fname)
                preview = self._file_preview(full_path)
                lines.append(f"- `{rel_path}`: {preview}")

        return "\n".join(lines) if lines else "(no files found)"

    def _file_preview(self, path: str, max_lines: int = 3) -> str:
        """Read first N lines of a file as a summary."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        lines.append(stripped)
                return " | ".join(lines) if lines else "(empty)"
        except Exception:
            return "(unreadable)"

    def compress_history(self, messages: list[dict]) -> list[dict]:
        """Compress conversation history to fit within token budget.

        Strategy: keep system + user (first) + last N tool exchanges.
        Approximate tokens as len(content) / 4.
        """
        if not messages:
            return messages

        # Always keep system and first user message
        kept = []
        rest = []
        for msg in messages:
            if msg["role"] in ("system", "user") and not kept:
                kept.append(msg)
            elif msg["role"] == "user" and len(kept) == 1:
                kept.append(msg)
            else:
                rest.append(msg)

        # Estimate tokens of kept messages
        kept_tokens = sum(len(str(m.get("content", ""))) // 4 for m in kept)
        budget = self.max_history_tokens - kept_tokens

        # Add messages from the end (most recent context is most valuable)
        included_from_end = []
        running_tokens = 0
        for msg in reversed(rest):
            msg_tokens = len(str(msg.get("content", ""))) // 4
            if running_tokens + msg_tokens > budget:
                break
            included_from_end.insert(0, msg)
            running_tokens += msg_tokens

        # If we dropped messages, add a compression notice
        dropped = len(rest) - len(included_from_end)
        if dropped > 0:
            kept.append({
                "role": "system",
                "content": f"[{dropped} earlier messages compressed to save context space]",
            })

        return kept + included_from_end
