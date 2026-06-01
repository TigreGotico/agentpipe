# MCP Server Configuration

MCP (Model Context Protocol) servers let you attach external tools (databases, APIs, documentation) that the agent can use during generation. Currently only supported for Claude.

## HTTP/SSE Servers

```python
from agentpipe import Agent, HttpMcpServer

agent = Agent("claude", mcp_servers=[
    HttpMcpServer(
        name="docs",
        url="http://localhost:9000/sse",
        headers={"Authorization": "Bearer tok"},
    ),
])

result = await agent.generate("Use the docs MCP to look up the API reference")
```

## Stdio Servers

```python
from agentpipe import Agent, StdioMcpServer

agent = Agent("claude", mcp_servers=[
    StdioMcpServer(
        name="github",
        command="npx",
        args=["-y", "@mcp/server-github"],
        env={"GITHUB_TOKEN": "ghp_x"},
    ),
])
```

## Multiple Servers

```python
agent = Agent("claude", mcp_servers=[
    HttpMcpServer(name="docs", url="http://localhost:9000/sse"),
    StdioMcpServer(name="github", command="npx", args=["-y", "@mcp/server-github"]),
])
```

At build time, these are serialized to a `--mcp-config` JSON blob passed to the Claude CLI. The JSON structure follows Claude's MCP config format:

```json
{
  "mcpServers": {
    "docs": {"type": "sse", "url": "http://localhost:9000/sse", "headers": {...}},
    "github": {"command": "npx", "args": ["-y", "@mcp/server-github"], "env": {...}}
  }
}
```

## Dataclass Fields

### HttpMcpServer

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | *(required)* | Server identifier |
| `url` | `str` | *(required)* | SSE endpoint URL |
| `headers` | `dict[str, str]` | `{}` | Optional HTTP headers |

### StdioMcpServer

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | *(required)* | Server identifier |
| `command` | `str` | *(required)* | Executable to run |
| `args` | `list[str]` | `[]` | Command arguments |
| `env` | `dict[str, str]` | `{}` | Environment variables |

# Approval Modes and Budget Caps

Approval modes and budget caps are Claude-specific features.

## Approval Modes

```python
from agentpipe import Agent, ApprovalMode

# Full auto — uses --dangerously-skip-permissions (default)
agent = Agent("claude")

# Plan mode (read-only, no tool execution)
agent = Agent("claude", approval_mode=ApprovalMode.PLAN)

# Auto-edit (auto-approve file edits, ask for shell commands)
agent = Agent("claude", approval_mode=ApprovalMode.AUTO_EDIT)

# Yolo mode — bypass all permissions
agent = Agent("claude", approval_mode=ApprovalMode.YOLO)

# Bypass — same as YOLO
agent = Agent("claude", approval_mode=ApprovalMode.BYPASS)
```

| ApprovalMode | Claude CLI Flag | Behavior |
|---|---|---|
| `DEFAULT` | `--dangerously-skip-permissions` | Full auto-approve |
| `AUTO_EDIT` | `--permission-mode acceptEdits` | Auto-approve edits, ask for shell |
| `YOLO` | `--dangerously-skip-permissions` | Bypass all permissions |
| `PLAN` | `--permission-mode plan` | Read-only, no execution |
| `BYPASS` | `--dangerously-skip-permissions` | Same as YOLO |

## Budget Caps

```python
# Cap spending at $1.00
agent = Agent("claude", max_budget_usd=1.00)

# Result will include usage with cost
result = await agent.generate_full("Refactor this module")
if result.usage:
    print(f"Cost: ${result.usage.cost_usd}")
```

The budget cap is passed as `--max-budget-usd` to the Claude CLI. The agent will stop generating once the budget is reached.