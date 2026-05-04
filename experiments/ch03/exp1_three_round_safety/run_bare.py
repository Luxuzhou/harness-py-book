"""Run the bare agent (Level 0) on a task. No harness layers."""
import os
import sys
import yaml
from harness import Harness


def main():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # 环境变量覆盖config.yaml（和主仓库.env体系对齐）
    config["api_key"] = os.environ.get("OPENAI_API_KEY", config.get("api_key", ""))
    config["base_url"] = os.environ.get("OPENAI_BASE_URL", config.get("base_url", "https://api.deepseek.com"))
    config["model"] = os.environ.get("OPENAI_MODEL", config.get("model", "deepseek-chat"))

    task = sys.argv[1] if len(sys.argv) > 1 else (
        "给 calculator.py 补全单元测试，覆盖减法、乘法和除法运算。"
    )

    print(f"=== BARE AGENT (Level 0) ===")
    print(f"Task: {task}\n")

    harness = Harness(
        api_key=config["api_key"],
        base_url=config["base_url"],
        model=config["model"],
        level=0,  # Bare: no safety, no context, no recovery
        max_steps=config.get("max_steps", 15),
    )

    result = harness.run(task)

    print(f"\n=== RESULT ===")
    print(f"Final response: {result['final_response'][:500]}")
    print(f"Steps: {result['metrics']['total_steps']}")
    print(f"Tokens: {result['metrics']['tokens_used']}")
    print(f"Tool calls: {len(result['metrics']['tool_calls'])}")
    print(f"Errors: {result['metrics']['errors']}")


if __name__ == "__main__":
    main()
