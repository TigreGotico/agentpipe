"""
List sessions and models — session management with OpenCode.

Usage:
    python -m examples.19_sessions_and_models
"""

import asyncio

from agentpipe import Agent


async def main():
    # List sessions
    agent = Agent("opencode-zen")
    print("=== Sessions ===")
    try:
        sessions = await agent.list_sessions()
        if sessions:
            for s in sessions[:5]:
                print(f"  {s.session_id} | {s.title or '(no title)'} | {s.provider}")
        else:
            print("  No sessions found.")
    except Exception as e:
        print(f"  Error: {e}")

    # List models
    print("\n=== Models ===")
    try:
        models = await agent.list_models()
        for m in models[:10]:
            print(f"  {m.id}")
        if len(models) > 10:
            print(f"  ... and {len(models) - 10} more")
    except Exception as e:
        print(f"  Error: {e}")

    # Stats
    print("\n=== Stats ===")
    try:
        stats = await agent.stats(days=7)
        if stats.get("raw"):
            print(f"  Raw output: {stats['raw'][:200]}...")
    except Exception as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
