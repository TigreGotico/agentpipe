# MCP Server Configuration

MCP (Model Context Protocol) servers let you attach external tools (databases, APIs, documentation) that the agent can use during generation.

## Inline MCP Configuration

### HTTP/SSE Servers (Claude, OpenCode)

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

OpenCode also supports inline HTTP MCP servers:

```python
agent = Agent("opencode", mcp_servers=[
    HttpMcpServer(name="api", url="http://localhost:8080/sse"),
])
```

### Stdio Servers (Claude, OpenCode)

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

### Multiple Servers

```python
agent = Agent("claude", mcp_servers=[
    HttpMcpServer(name="docs", url="http://localhost:9000/sse"),
    StdioMcpServer(name="github", command="npx", args=["-y", "@mcp/server-github"]),
])
```

At build time, these are serialized to a JSON blob passed via `--mcp-config` (Claude) or the provider's MCP config (OpenCode). The JSON structure follows Claude's MCP config format:

```json
{
  "mcpServers": {
    "docs": {"type": "sse", "url": "http://localhost:9000/sse", "headers": {...}},
    "github": {"command": "npx", "args": ["-y", "@mcp/server-github"], "env": {...}}
  }
}
```

### Provider Support

| Feature | Claude | Gemini | OpenCode |
|---------|--------|--------|----------|
| Inline HTTP MCP | `--mcp-config` | Config only | Config only |
| Inline Stdio MCP | `--mcp-config` | n/a | Config only |
| `mcp_add()` | `claude mcp add` | n/a | `opencode mcp add` |
| `mcp_remove()` | `claude mcp remove` | n/a | `opencode mcp remove` |
| `mcp_list()` | `claude mcp list` | n/a | `opencode mcp list` |

## Programmatic MCP Management

Add, remove, and list MCP servers at runtime:

```python
from agentpipe import Agent

agent = Agent("claude")

# Add an SSE server
await agent.mcp_add("docs", url="http://localhost:9000/sse")

# Add a stdio server
await agent.mcp_add("github", command="npx", args=["-y", "@mcp/server-github"],
                    env={"GITHUB_TOKEN": "ghp_x"})

# List all configured servers
servers = await agent.mcp_list()

# Remove a server
await agent.mcp_remove("github")
```

### MCP Server Dataclass Fields

#### HttpMcpServer

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | *(required)* | Server identifier |
| `url` | `str` | *(required)* | SSE endpoint URL |
| `headers` | `dict[str, str]` | `{}` | Optional HTTP headers |

#### StdioMcpServer

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | *(required)* | Server identifier |
| `command` | `str` | *(required)* | Executable to run |
| `args` | `list[str]` | `[]` | Command arguments |
| `env` | `dict[str, str]` | `{}` | Environment variables |

# Approval Modes

All three providers support approval modes, mapped to their native CLI flags.

## Claude

```python
from agentpipe import Agent, ApprovalMode

# full auto: uses --dangerously-skip-permissions (default)
agent = Agent("claude")

# Plan mode (read-only, no tool execution)
agent = Agent("claude", approval_mode=ApprovalMode.PLAN)

# Auto-edit (auto-approve file edits, ask for shell commands)
agent = Agent("claude", approval_mode=ApprovalMode.AUTO_EDIT)

# yolo mode: bypass all permissions
agent = Agent("claude", approval_mode=ApprovalMode.YOLO)

# bypass: same as YOLO
agent = Agent("claude", approval_mode=ApprovalMode.BYPASS)
```

| ApprovalMode | Claude CLI Flag | Behavior |
|---|---|---|
| `DEFAULT` | `--dangerously-skip-permissions` | Full auto-approve |
| `AUTO_EDIT` | `--permission-mode acceptEdits` | Auto-approve edits, ask for shell |
| `YOLO` | `--dangerously-skip-permissions` | Bypass all permissions |
| `PLAN` | `--permission-mode plan` | Read-only, no execution |
| `BYPASS` | `--dangerously-skip-permissions` | Same as YOLO |

## Gemini

```python
from agentpipe import Agent, ApprovalMode

# yolo/bypass: auto-approve all
agent = Agent("gemini", approval_mode=ApprovalMode.YOLO)

# plan: read-only mode
agent = Agent("gemini", approval_mode=ApprovalMode.PLAN)

# Auto-edit
agent = Agent("gemini", approval_mode=ApprovalMode.AUTO_EDIT)
```

| ApprovalMode | Gemini CLI Flag | Behavior |
|---|---|---|
| `DEFAULT` | n/a | Normal approval |
| `AUTO_EDIT` | `--approval-mode auto_edit` | Auto-approve edits |
| `YOLO` | `--yolo` | Auto-approve all tools |
| `PLAN` | `--approval-mode plan` | Read-only |
| `BYPASS` | `--yolo` | Same as YOLO |

## Kilo Code

```python
from agentpipe import Agent, ApprovalMode

# auto mode: confirm each action (non-YOLO)
agent = Agent("kilo", approval_mode=ApprovalMode.PLAN)

# Bypass permissions (default for non-interactive runs)
agent = Agent("kilo", approval_mode=ApprovalMode.YOLO)
```

| ApprovalMode | Kilo CLI Flag | Behavior |
|---|---|---|
| `DEFAULT` / `PLAN` | `--auto` | Confirm actions |
| `YOLO` / `BYPASS` | `--dangerously-skip-permissions` | Bypass all permissions |

## OpenCode

```python
from agentpipe import Agent, ApprovalMode

# Bypass permissions (default for non-interactive runs)
agent = Agent("opencode", approval_mode=ApprovalMode.YOLO)

# explicit plan mode: no --dangerously-skip-permissions
agent = Agent("opencode", approval_mode=ApprovalMode.PLAN)
```

| ApprovalMode | OpenCode CLI Flag | Behavior |
|---|---|---|
| `DEFAULT` | n/a | `--dangerously-skip-permissions` |
| `YOLO` | `--dangerously-skip-permissions` | Bypass all permissions |
| `BYPASS` | `--dangerously-skip-permissions` | Same as YOLO |

## Aider

```python
from agentpipe import Agent, ApprovalMode

# Aider always uses --yes-always for headless mode (no interactive prompts)
agent = Agent("aider", approval_mode=ApprovalMode.YOLO)
```

Aider does not have fine-grained approval modes. It always sets `--yes-always` in headless operation.

When `approval_mode` is `None` (the default), all providers use their most permissive mode for non-interactive execution.

## Budget Caps (Claude only)

```python
# Cap spending at $1.00
agent = Agent("claude", max_budget_usd=1.00)

result = await agent.generate_full("Refactor this module")
if result.usage:
    print(f"Cost: ${result.usage.cost_usd}")
```

The budget cap is passed as `--max-budget-usd` to the Claude CLI. The agent will stop generating once the budget is reached.

---
[← HTTP Server](server.md) · [Home](index.md) · [Auth and Quota →](auth-quota.md)