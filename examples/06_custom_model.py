"""
Custom model override — use a specific model on any provider.

Usage:
    python -m examples.06_custom_model
"""

import asyncio

from agentpipe import Agent


async def main():
    # Override the default model on each provider
    agents = [
        Agent("claude", model="haiku"),
        Agent("gemini", model="gemini-2.5-pro"),
        Agent("opencode-free", model="opencode/deepseek-v4-flash-free"),
        Agent("opencode-go", model="opencode-go/kimi-k2.6"),
    ]

    prompt = "What is 2+2? Answer with just the number."

    for agent in agents:
        print(f"\n--- {agent.provider}/{agent.model} ---")
        try:
            result = await agent.generate(prompt, timeout=30)
            print(result.strip())
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
