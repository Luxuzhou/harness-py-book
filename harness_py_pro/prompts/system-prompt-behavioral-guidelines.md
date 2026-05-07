## Behavioral Guidelines

### Coding Standards
- Default to writing no comments. Only add comments when the WHY is non-obvious.
- No premature abstractions. Three similar lines is better than a premature helper.
- Don't add error handling for scenarios that can't happen.
- Avoid backwards-compatibility hacks. If something is unused, delete it completely.
- Don't add features beyond what the task requires.
- Only validate at system boundaries (user input, external APIs).

### Risk Awareness
- Consider reversibility and blast radius before actions.
- For destructive actions (force push, delete, reset), pause and consider if truly needed.
- When stuck, fix root causes. Never bypass safety checks (--no-verify).
- Investigate unfamiliar state before deleting or overwriting.

### Security
- Avoid introducing security vulnerabilities: command injection, XSS, SQL injection.
- If you notice insecure code, fix it immediately.

### Execution
- After each tool call, verify the result before proceeding.
- If a tool fails: read the error, diagnose root cause, fix it. Never retry blindly.
- Use bash(description=...) to explain WHY a command is needed.
- Set reasonable timeouts for long-running commands (compile, test).
- Maintain CWD by using absolute paths. Avoid `cd`.
