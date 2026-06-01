"""
Convenience cascade functions — cascade_coding, cascade_fast_free, cascade_free_only.

Usage:
    python -m examples.09_cascade_convenience
"""

import asyncio

from agentpipe import cascade_coding, cascade_fast_free, cascade_free_only


async def main():
    print("=== cascade_coding (coding profile, stops at CHEAP tier) ===")
    r1 = await cascade_coding("Write a Python function to reverse a string.", per_attempt_timeout=30)
    print(f"  Model: {r1.successful_model} | Time: {r1.total_duration_seconds:.1f}s")
    print(f"  Answer: {r1.text[:150]}...\n")

    print("=== cascade_fast_free (fast free models only) ===")
    r2 = await cascade_fast_free("What is the Fibonacci sequence?", per_attempt_timeout=30)
    print(f"  Model: {r2.successful_model} | Time: {r2.total_duration_seconds:.1f}s")
    print(f"  Answer: {r2.text[:150]}...\n")

    print("=== cascade_free_only (all free models, no cost) ===")
    r3 = await cascade_free_only("Explain recursion in one sentence.", per_attempt_timeout=30)
    print(f"  Model: {r3.successful_model} | Time: {r3.total_duration_seconds:.1f}s")
    print(f"  Answer: {r3.text[:150]}...\n")


if __name__ == "__main__":
    asyncio.run(main())
