"""
OpenCode plans — Free, Zen, Go provider comparison.

Usage:
    python -m examples.18_opencode_plans
"""

import asyncio

from agentpipe import Agent


async def main():
    plans = [
        ("opencode-free", "opencode/big-pickle", "free"),
        ("opencode-zen", "opencode/gemini-3-flash", "zen"),
        ("opencode-go", "opencode-go/deepseek-v4-flash", "go"),
    ]

    for provider, default_model, plan in plans:
        agent = Agent(provider)
        print(f"=== {provider} (plan={plan}) ===")
        print(f"  Default model: {agent.model}")
        print(f"  Expected:      {default_model}")
        print(f"  Provider inst: {type(agent._provider_instance).__name__}")
        print(f"  Plan property: {agent._provider_instance.plan}")
        assert agent.model == default_model
        assert agent._provider_instance.plan == plan
        print()

    # Override model on Go plan
    go_agent = Agent("opencode-go", model="opencode-go/kimi-k2.6")
    print(f"Custom Go model: {go_agent.model}")
    print(f"Still Go plan:   {go_agent._provider_instance.plan}")


if __name__ == "__main__":
    asyncio.run(main())
