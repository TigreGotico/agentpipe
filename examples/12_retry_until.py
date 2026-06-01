"""
retry_until — keep trying until a validator function passes.

Usage:
    python -m examples.12_retry_until
"""

import asyncio

from agentpipe import Agent, retry_until


async def main():
    agent = Agent("gemini-flash")

    print("=== Retry until output contains '42' ===\n")

    result = await retry_until(
        agent,
        "Tell me the answer to life, the universe, and everything.",
        validator=lambda text: "42" in text,
        max_attempts=3,
        refine_prompt="Your previous answer did not contain the number 42. Please include it.",
        timeout=60,
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())
