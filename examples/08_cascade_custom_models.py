"""
Cascade with explicit model list and progress callback.

Usage:
    python -m examples.08_cascade_custom_models
"""

import asyncio

from agentpipe import cascade


def log_attempt(attempt):
    status = "OK" if attempt.success else f"FAIL ({attempt.error_type})"
    cost = f"${attempt.cost_usd:.4f}" if attempt.cost_usd else ""
    print(f"  {attempt.model:40s} {status:20s} {attempt.duration_seconds:.1f}s {cost}")


async def main():
    models = [
        "opencode/big-pickle",
        "opencode/deepseek-v4-flash-free",
        "opencode/gemini-3-flash",
        "opencode/kimi-k2.5",
    ]

    print(f"=== Custom cascade with {len(models)} models ===\n")

    result = await cascade(
        "Explain the difference between a list and a tuple in Python.",
        models=models,
        per_attempt_timeout=30,
        retry_delay_seconds=1,
        on_attempt=log_attempt,
    )

    print(f"\nFinal answer from {result.successful_model} ({result.successful_provider}):")
    print(result.text[:300] + "..." if len(result.text) > 300 else result.text)
    print(f"\nTotal time: {result.total_duration_seconds:.1f}s | Attempts: {result.attempt_count}")


if __name__ == "__main__":
    asyncio.run(main())
