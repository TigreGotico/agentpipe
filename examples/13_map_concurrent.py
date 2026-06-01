"""
map_concurrent — send the same prompt to multiple agents.

Usage:
    python -m examples.13_map_concurrent
"""

import asyncio

from agentpipe import Agent, map_concurrent


async def main():
    agents = [
        Agent("opencode-free"),
        Agent("gemini-flash"),
    ]

    prompt = "Explain gravity in exactly one sentence."

    print(f"Sending prompt to {len(agents)} agents:\n")

    results = await map_concurrent(agents, prompt, timeout=30)

    for agent, result in zip(agents, results, strict=False):
        print(f"--- {agent.provider}/{agent.model} ---")
        print(f"{result.strip()}\n")


if __name__ == "__main__":
    asyncio.run(main())
