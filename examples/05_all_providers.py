"""
All provider aliases — demonstrates every provider shortcut and its default model.

Usage:
    python -m examples.05_all_providers
"""

import asyncio

from agentpipe import Agent

PROVIDERS = [
    ("claude", "sonnet"),
    ("claude-sonnet", "sonnet"),
    ("claude-haiku", "haiku"),
    ("claude-opus", "opus"),
    ("gemini", "gemini-2.5-flash"),
    ("gemini-flash", "gemini-2.5-flash"),
    ("gemini-pro", "gemini-2.5-pro"),
    ("opencode", "opencode/gemini-3-flash"),
    ("opencode-free", "opencode/big-pickle"),
    ("opencode-zen", "opencode/gemini-3-flash"),
    ("opencode-go", "opencode-go/deepseek-v4-flash"),
]


async def main():
    for provider_name, expected_model in PROVIDERS:
        agent = Agent(provider_name)
        print(f"Agent('{provider_name:20s}') → provider={agent.provider:20s} model={agent.model}")
        assert agent.model == expected_model, f"Expected {expected_model}, got {agent.model}"

    print(f"\nAll {len(PROVIDERS)} provider aliases verified.")


if __name__ == "__main__":
    asyncio.run(main())
