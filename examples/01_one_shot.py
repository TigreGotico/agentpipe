"""
One-shot generation — the simplest possible usage.

Usage:
    python -m examples.01_one_shot
"""

import asyncio

from agentpipe import Agent


async def main():
    agent = Agent("gemini-flash")

    result = await agent.generate("Give me a one-sentence explanation of async/await in Python.")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
