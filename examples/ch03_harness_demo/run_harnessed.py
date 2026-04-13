"""Run the fully harnessed agent (Level 4) on a task."""
import os
import sys
import yaml
from harness import Harness


def main():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # 环境变量覆盖config.yaml
    config["api_key"] = os.environ.get("OPENAI_API_KEY", config.get("api_key", ""))
    config["base_url"] = os.environ.get("OPENAI_BASE_URL", config.get("base_url", "https://api.deepseek.com"))
    config["model"] = os.environ.get("OPENAI_MODEL", config.get("model", "deepseek-chat"))

    task = sys.argv[1] if len(sys.argv) > 1 else (
        "给 calculator.py 补全单元测试，覆盖减法、乘法和除法运算。"
    )

    print(f"=== FULL HARNESS (Level 4) ===")
    print(f"Task: {task}\n")

    harness = Harness(
        api_key=config["api_key"],
        base_url=config["base_url"],
        model=config["model"],
        project_dir="target_project",
        level=4,  # Full harness: all layers active
        project_rules=config.get("project_rules", {}),
        allowed_paths=[os.path.abspath("target_project")],
        command_blacklist=config.get("command_blacklist"),
        max_steps=config.get("max_steps", 15),
    )

    result = harness.run(task)

    print(f"\n=== RESULT ===")
    print(f"Final response: {result['final_response'][:500]}")
    print(f"Steps: {result['metrics']['total_steps']}")
    print(f"Tokens: {result['metrics']['tokens_used']}")
    print(f"Tool calls: {len(result['metrics']['tool_calls'])}")
    print(f"Errors: {result['metrics']['errors']}")

    if result["safety_stats"]:
        stats = result["safety_stats"]
        print(f"\n--- Safety Stats ---")
        print(f"Blocked: {stats['blocked_count']}")
        print(f"Warnings: {stats['warning_count']}")
        for b in stats["blocked_details"]:
            print(f"  - {b['message']}")

    if result["recovery_stats"]:
        stats = result["recovery_stats"]
        print(f"\n--- Recovery Stats ---")
        print(f"Retries: {stats['total_retries']}")
        print(f"Failures: {stats['total_failures']}")
        print(f"Safe mode: {stats['safe_mode_entered']}")


if __name__ == "__main__":
    main()
