"""
Full result with usage tracking — get text, events, session ID, and token counts.

Usage:
    python -m examples.02_full_result
"""

import asyncio

from agentpipe import Agent


async def main():
    agent = Agent("opencode-free")

    result = await agent.generate_full("What are the 5 SOLID principles? One line each.")

    print(f"Text:       {result.text}")
    print(f"Session ID: {result.session_id}")
    print(f"Returncode: {result.returncode}")
    print(f"Events:     {len(result.events)} events")

    if result.usage:
        print(f"Input tokens:  {result.usage.input_tokens}")
        print(f"Output tokens: {result.usage.output_tokens}")
        print(f"Cost:          ${result.usage.cost_usd or 0:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
