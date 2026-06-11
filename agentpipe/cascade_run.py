"""Run a prompt through the model cascade, falling back across free and cheap models.

Usage:
    python -m agentpipe.cascade_run "Explain this code"
    python -m agentpipe.cascade_run --profile coding "Write tests for foo.py"
    python -m agentpipe.cascade_run --models "opencode/big-pickle,gemini-2.5-flash" "Summarize"
    python -m agentpipe.cascade_run --free-only "Quick question"
    python -m agentpipe.cascade_run --max-tier cheap "Refactor module"
    python -m agentpipe.cascade_run --max-attempts 5 --timeout 60 "Prompt"
"""

from __future__ import annotations

import argparse
import asyncio
import json

from .cascade import CASCADE_PROFILES, ModelTier, cascade


def _tier_from_name(name: str) -> ModelTier:
    return {"free": ModelTier.FREE, "cheap": ModelTier.CHEAP, "mid": ModelTier.MID, "premium": ModelTier.PREMIUM}[name]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run a prompt through the model cascade",
        prog="agentpipe cascade",
    )
    parser.add_argument("prompt", help="The prompt to send")
    parser.add_argument(
        "--profile",
        default="default",
        choices=list(CASCADE_PROFILES),
        help="Cascade profile (default: default)",
    )
    parser.add_argument("--models", help="Comma-separated model list (overrides profile)")
    parser.add_argument("--free-only", action="store_true", help="Only try free models")
    parser.add_argument(
        "--max-tier",
        choices=["free", "cheap", "mid", "premium"],
        help="Stop escalating beyond this tier",
    )
    parser.add_argument("--max-attempts", type=int, default=10, help="Max models to try (default: 10)")
    parser.add_argument("--max-cost", type=float, help="Stop if cumulative cost exceeds $USD")
    parser.add_argument("--timeout", type=int, default=120, help="Per-attempt timeout in seconds (default: 120)")
    parser.add_argument("--cwd", default="/tmp", help="Working directory (default: /tmp)")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args(argv)

    if args.models:
        models = [m.strip() for m in args.models.split(",")]
        profile = "default"
    else:
        models = None
        profile = "free-only" if args.free_only else args.profile

    max_tier = _tier_from_name(args.max_tier) if args.max_tier else None

    result = asyncio.run(
        cascade(
            args.prompt,
            models=models,
            profile=profile,
            max_tier=max_tier,
            max_attempts=args.max_attempts,
            max_cost_usd=args.max_cost,
            per_attempt_timeout=args.timeout,
            cwd=args.cwd,
            retry_delay_seconds=2,
        )
    )

    if args.json:
        print(
            json.dumps(
                {
                    "text": result.text,
                    "successful_model": result.successful_model,
                    "successful_provider": result.successful_provider,
                    "attempts": [
                        {
                            "model": a.model,
                            "provider": a.provider,
                            "success": a.success,
                            "error_type": a.error_type.value if a.error_type else None,
                            "error_message": a.error_message,
                            "duration_seconds": a.duration_seconds,
                            "cost_usd": a.cost_usd,
                        }
                        for a in result.attempts
                    ],
                    "total_cost_usd": result.total_cost_usd,
                    "total_duration_seconds": result.total_duration_seconds,
                },
                indent=2,
            )
        )
    else:
        print(f"[OK] {result.successful_provider}/{result.successful_model}")
        print()
        print(result.text)
        print()
        failed = result.failed_attempts
        if failed:
            print(f"[{len(failed)} failed attempt(s)]")
            for a in failed:
                print(f"  {a.model}: {a.error_type.value} - {a.error_message}")
            print()
        print(
            f"Attempts: {result.attempt_count} | "
            f"Cost: ${result.total_cost_usd:.4f} | "
            f"Time: {result.total_duration_seconds:.1f}s"
        )


if __name__ == "__main__":
    main()
