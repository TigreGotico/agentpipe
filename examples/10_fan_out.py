"""
Fan-out — send multiple prompts to the same agent concurrently.

Usage:
    python -m examples.10_fan_out
"""

import asyncio

from agentpipe import Agent, fan_out


async def main():
    agent = Agent("gemini-flash", timeout=60)

    prompts = [
        "What is the capital of Japan?",
        "What is the capital of Brazil?",
        "What is the capital of Australia?",
        "What is the capital of Egypt?",
        "What is the capital of Canada?",
    ]

    print(f"Sending {len(prompts)} prompts to {agent.provider}/{agent.model}...\n")

    results = await fan_out(agent, prompts, max_concurrency=3)

    for prompt, result in zip(prompts, results, strict=False):
        print(f"Q: {prompt}")
        print(f"A: {result.strip()}\n")


if __name__ == "__main__":
    asyncio.run(main())
