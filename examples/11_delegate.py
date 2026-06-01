"""
Delegate — draft with a cheap model, review with a stronger one.

Usage:
    python -m examples.11_delegate
"""

import asyncio

from agentpipe import Agent, delegate


async def main():
    drafter = Agent("opencode-free")
    reviewer = Agent("gemini-flash")

    print("=== Draft with opencode-free, review with gemini-flash ===\n")

    result = await delegate(
        drafter,
        reviewer,
        "Write a Python function that checks if a string is a palindrome.",
        "Review this code for correctness, edge cases, and Python style.",
        timeout=120,
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())
