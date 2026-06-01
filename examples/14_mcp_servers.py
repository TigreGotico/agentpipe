"""
MCP server configuration — attach tools to Claude.

Usage:
    python -m examples.14_mcp_servers
"""

import asyncio

from agentpipe import Agent, HttpMcpServer, StdioMcpServer


async def main():
    agent = Agent(
        "claude-sonnet",
        mcp_servers=[
            HttpMcpServer(
                name="docs",
                url="http://localhost:9000/sse",
                headers={"Authorization": "Bearer my-secret-token"},
            ),
            StdioMcpServer(
                name="github",
                command="npx",
                args=["-y", "@mcp/server-github"],
                env={"GITHUB_TOKEN": "ghp_xxxxxxxxxxxx"},
            ),
        ],
        cwd="/tmp",
    )

    print(f"Agent: {agent.provider}/{agent.model}")
    print(f"MCP servers: {[s.name for s in agent.mcp_servers]}")
    print(f"cwd: {agent.cwd}")

    # Live call (requires MCP servers running):
    # result = await agent.generate("Use the docs MCP to search for 'authentication'")  # noqa: ERA001
    # print(result)  # noqa: ERA001


if __name__ == "__main__":
    asyncio.run(main())
