"""
Auth status and quota checking.

Usage:
    python -m examples.16_auth_and_quota
"""

import asyncio

from agentpipe import check_quota


async def main():
    for provider in ["claude", "gemini", "opencode", "opencode-go"]:
        print(f"=== {provider} ===")
        try:
            status = await check_quota(provider)
            print(f"  Authenticated:  {status.authenticated}")
            print(f"  Subscription:     {status.subscription_type}")
            print(f"  Email:           {status.email}")
            print(f"  Rate limited:    {status.rate_limited}")
            if status.rate_limit_resets_in_seconds:
                print(f"  Resets in:       {status.rate_limit_resets_in_seconds}s")
            if status.available_models:
                print(f"  Models:          {len(status.available_models)}")
            if status.usage_stats:
                print(f"  Usage stats:     {list(status.usage_stats.keys())}")
        except Exception as e:
            print(f"  Error: {e}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
