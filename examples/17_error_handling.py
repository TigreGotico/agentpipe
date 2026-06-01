"""
Error handling — catching AgentProcessError and parsing rate limits.

Usage:
    python -m examples.17_error_handling
"""

import asyncio

from agentpipe import Agent, AgentProcessError, parse_rate_limit_error


async def main():
    agent = Agent("gemini-flash", timeout=10)

    try:
        result = await agent.generate("Hello, world!")
        print(f"Success: {result[:100]}")
    except AgentProcessError as e:
        print("AgentProcessError caught:")
        print(f"  Returncode: {e.returncode}")
        print(f"  Argv:       {e.argv}")
        print(f"  Stderr:     {e.stderr[:200]}")

        # Parse for rate-limit information
        info = parse_rate_limit_error("gemini", e)
        print("\n  Rate limit info:")
        print(f"  rate_limited:    {info['rate_limited']}")
        print(f"  resets_in:       {info['resets_in_seconds']}s")
    except asyncio.TimeoutError:
        print("Timed out!")
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
