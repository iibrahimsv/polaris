import asyncio
from enhanced_agent_runner import EnhancedAgentRunner


async def main():
    runner = EnhancedAgentRunner()

    # Choose one that fits your current task:
    agent_configs = {
        "ml_engineer": {
            "name": "ML Engineering Assistant",
            "prompt": "You are an expert ML Engineer specializing in "
                      "model development, data pipelines, "
                      "and production ML systems."
        },
    }

    config = agent_configs["ml_engineer"]  # <-- Change this

    result = await runner.run_agent_task(
        "Create a Python script that generates Fibonacci numbers with error handling",
        agent_name=config["name"],
        system_prompt=config["prompt"]
    )

    if result.success:
        print("✅ Success!")
    else:
        print(f"❌ Error: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
