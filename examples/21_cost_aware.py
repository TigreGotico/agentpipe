"""
Cost-aware pipeline — draft with free models, cap total spending.

Usage:
    python -m examples.21_cost_aware
"""

import asyncio

from agentpipe import Agent, ModelTier, cascade, delegate


async def main():
    # Strategy 1: Delegate from free to cheap
    print("=== Delegate: free draft → cheap review ===")
    result = await delegate(
        Agent("opencode-free"),
        Agent("opencode-zen"),
        "Write a Python one-liner to flatten a nested list.",
        "Review for correctness and edge cases.",
        timeout=60,
    )
    print(f"{result[:200]}...\n")

    # Strategy 2: Cascade with cost cap
    print("=== Cascade with cost cap ($0.10 max) ===")
    result2 = await cascade(
        "Explain the difference between shallow and deep copy.",
        profile="coding",
        max_tier=ModelTier.CHEAP,
        max_cost_usd=0.10,
        per_attempt_timeout=30,
    )
    print(f"Success: {result2.successful_model}")
    print(f"Cost: ${result2.total_cost_usd:.4f}")
    print(f"Attempts: {result2.attempt_count}")
    print(f"Answer: {result2.text[:150]}...\n")

    # Strategy 3: Free-only cascade — zero cost guaranteed
    print("=== Free-only cascade (zero cost) ===")
    result3 = await cascade(
        "What is the time complexity of binary search?",
        profile="free-only",
        max_tier=ModelTier.FREE,
        per_attempt_timeout=30,
    )
    print(f"Success: {result3.successful_model}")
    print(f"Cost: ${result3.total_cost_usd:.4f}")
    print(f"Answer: {result3.text[:150]}...")


if __name__ == "__main__":
    asyncio.run(main())
