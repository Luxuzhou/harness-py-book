"""A calculator module with intentional issues for the harness demo."""
import json
from datetime import datetime


class Calculator:
    """Calculator with history tracking.

    Intentional problems:
    - Bug: division by zero not handled
    - Code smell: God Function (calculate does too much)
    - Magic number: hardcoded precision 0.0001
    """

    def __init__(self):
        self.history = []

    def calculate(self, a, op, b):
        """God Function: computes, logs history, formats output — all in one."""
        # Compute
        if op == "+":
            result = a + b
        elif op == "-":
            result = a - b
        elif op == "*":
            result = a * b
        elif op == "/":
            result = a / b  # BUG: no ZeroDivisionError handling
        else:
            raise ValueError(f"Unknown operator: {op}")

        # Round with magic number
        if isinstance(result, float) and abs(result - round(result)) < 0.0001:
            result = round(result)

        # Log history (should be separate responsibility)
        entry = {
            "expression": f"{a} {op} {b}",
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
        self.history.append(entry)

        # Format output (should be separate responsibility)
        formatted = f"{a} {op} {b} = {result}"

        return {"result": result, "formatted": formatted, "entry": entry}

    def get_history(self):
        """Return calculation history."""
        return self.history

    def export_history(self, filepath):
        """Export history to JSON file."""
        with open(filepath, "w") as f:
            json.dump(self.history, f, indent=2)
