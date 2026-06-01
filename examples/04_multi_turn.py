"""
Multi-turn session with auto-resume — carries context across turns.

Usage:
    python -m examples.04_multi_turn
"""

import asyncio

from agentpipe import Agent


async def main():
    agent = Agent("opencode-zen", cwd="/tmp")

    async with agent.session() as sess:
        print("=== Turn 1 ===")
        r1 = await sess.generate("Name 3 programming languages beginning with P.")
        print(r1)

        print("\n=== Turn 2 ===")
        r2 = await sess.generate("Which of those is best for web development and why?")
        print(r2)

        print("\n=== Turn 3 ===")
        r3 = await sess.generate("Write a one-line hello world in that language.")
        print(r3)

        print("\n=== Session Stats ===")
        print(f"Session ID:     {sess.session_id}")
        print(f"Total turns:    {sess.usage.turn_count}")
        print(f"Input tokens:   {sess.usage.total_input_tokens}")
        print(f"Output tokens:  {sess.usage.total_output_tokens}")
        if sess.usage.total_cost_usd:
            print(f"Total cost:     ${sess.usage.total_cost_usd:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
