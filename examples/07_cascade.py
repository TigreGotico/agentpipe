"""
Model cascade — try free models first, escalate on failure.

Usage:
    python -m examples.07_cascade
"""

import asyncio

from agentpipe import ModelTier, cascade


async def main():
    print("=== Default cascade (start free, escalate) ===")
    result = await cascade("Explain quantum entanglement in one paragraph.", per_attempt_timeout=30)
    print(f"Success: {result.successful_model} via {result.successful_provider}")
    print(f"Attempts: {result.attempt_count}, Time: {result.total_duration_seconds:.1f}s")
    print(f"Answer: {result.text[:200]}...")
    print()

    for attempt in result.attempts:
        status = "OK" if attempt.success else f"{attempt.error_type}"
        print(f"  {attempt.model:40s} ({attempt.provider:15s}): {status} [{attempt.duration_seconds:.1f}s]")

    print("\n=== Free-only cascade ===")
    result2 = await cascade("What is the capital of France?", profile="free-only", per_attempt_timeout=30)
    print(f"Success: {result2.successful_model} via {result2.successful_provider}")

    print("\n=== CHEAP tier cap ===")
    result3 = await cascade("Write a haiku about programming.", max_tier=ModelTier.CHEAP, per_attempt_timeout=30)
    print(f"Success: {result3.successful_model} via {result3.successful_provider}")


if __name__ == "__main__":
    asyncio.run(main())
