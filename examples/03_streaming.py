"""
Streaming events — process tool calls, thinking text, and usage in real time.

Usage:
    python -m examples.03_streaming
"""

import asyncio

from agentpipe import Agent, ThinkingEvent, ToolCallEvent, ToolResultEvent, UsageEvent


async def main():
    agent = Agent("claude-sonnet", cwd="/tmp")

    print("Streaming response:\n")
    async for event in agent.generate_stream("List the files in /tmp and tell me what you find."):
        match event:
            case ThinkingEvent(text=text):
                print(text, end="", flush=True)
            case ToolCallEvent(tool=tool):
                print(f"\n[calling tool: {tool}]")
            case ToolResultEvent(tool=tool, output=output):
                preview = output[:100].replace("\n", " ")
                print(f"[{tool} result: {preview}...]")
            case UsageEvent(input_tokens=n, output_tokens=m):
                print(f"\n[usage: {n} input, {m} output tokens]")


if __name__ == "__main__":
    asyncio.run(main())
