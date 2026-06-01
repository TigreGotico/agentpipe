# agentpipe

Async Python wrapper for coding agent CLIs (Claude Code, Gemini, Opencode).

## Install

```bash
uv add agentpipe
```

Provider CLIs (`claude`, `gemini`, `opencode`) must be installed and authenticated separately.

## Quick Start

```python
from agentpipe import Agent

# Default free-tier models, cwd defaults to /tmp
agent = Agent("gemini")          # model=gemini-2.5-flash
agent = Agent("opencode")       # model=opencode/gemini-3-flash
agent = Agent("claude")         # model=sonnet
agent = Agent("claude", model="opus", cwd="/home/user/project")

# One-shot
result = await agent.generate("Summarize this repo", cwd=".")
print(result)

# Multi-turn session with auto-resume
async with agent.session(cwd=".") as sess:
    r1 = await sess.generate("List key modules")
    r2 = await sess.generate("Which is riskiest?")  # auto-resumes
    print(sess.session_id)
    print(sess.usage.total_input_tokens)  # accumulated across turns
    print(sess.usage.total_cost_usd)

# Streaming events
async for event in agent.generate_stream("Explain architecture"):
    match event:
        case ThinkingEvent(text=t): print(t, end="")
        case ToolCallEvent(tool=name): print(f"[tool: {name}]")
        case UsageEvent(input_tokens=n): print(f"Tokens: {n}")

# Full result with events and usage
result = await agent.generate_full("Explain the architecture")
print(result.text)
print(result.events)
print(result.usage)
print(result.session_id)
```

## Delegation and Pipelines

```python
from agentpipe import Agent, delegate, fan_out, retry_until, map_concurrent

cheap = Agent("gemini")
expensive = Agent("claude")

# Cheap drafts, expensive reviews
final = await delegate(cheap, expensive, "Write tests", "Review for correctness")

# Fan-out: generate N prompts concurrently (semaphore-capped)
results = await fan_out(cheap, ["prompt A", "prompt B", "prompt C"], max_concurrency=3)

# Retry until validator passes
result = await retry_until(agent, "Fix this bug", validator=lambda r: "no errors" in r.lower())

# Same prompt to multiple agents
results = await map_concurrent([Agent("claude"), Agent("gemini")], "explain this")
```

## MCP Server Configuration (Claude only)

```python
from agentpipe import Agent, HttpMcpServer, StdioMcpServer

agent = Agent("claude", mcp_servers=[
    HttpMcpServer(name="docs", url="http://localhost:9000/sse", headers={"Authorization": "Bearer tok"}),
    StdioMcpServer(name="github", command="npx", args=["-y", "@mcp/server-github"], env={"GITHUB_TOKEN": "ghp_x"}),
])
result = await agent.generate("Use the MCP tools to inspect the repo")
```

## Approval Modes and Budget Caps (Claude only)

```python
from agentpipe import Agent, ApprovalMode

# Full auto-approve (default)
agent = Agent("claude")  # uses --dangerously-skip-permissions

# Plan mode (read-only)
agent = Agent("claude", approval_mode=ApprovalMode.PLAN)

# Budget cap
agent = Agent("claude", max_budget_usd=1.0)  # uses --max-budget-usd
```

## Auth Status

```python
agent = Agent("claude")
status = await agent.auth_status()
print(status.authenticated, status.email, status.subscription_type)
# AuthStatus(authenticated=True, provider='claude', email='user@example.com', ...)
```

## Session Management

```python
agent = Agent("gemini")

# List sessions (Gemini, Opencode)
sessions = await agent.list_sessions()
for s in sessions:
    print(s.session_id, s.title)

# Opencode also supports stats and model listing
agent = Agent("opencode")
models = await agent.list_models()      # list[ModelInfo]
stats = await agent.stats(days=7)       # dict with raw stats output
```

## Usage Tracking

```python
async with agent.session() as sess:
    r1 = await sess.generate("prompt 1")
    print(sess.usage.total_input_tokens)   # accumulated across turns
    print(sess.usage.total_output_tokens)
    print(sess.usage.total_cost_usd)
    print(sess.usage.turn_count)

    r2 = await sess.generate("prompt 2")
    print(sess.usage.total_input_tokens)   # now includes both turns
```

## Event Types

| Event | Fields | When |
|-------|--------|------|
| `ThinkingEvent` | `text` | Model text output |
| `ToolCallEvent` | `tool`, `args`, `tool_id` | Tool invocation start |
| `ToolResultEvent` | `tool`, `output`, `exit_code`, `duration_ms` | Tool execution result |
| `UsageEvent` | `input_tokens`, `output_tokens`, `cost_usd`, `cache_read_tokens`, `cache_write_tokens` | Per-step token usage |

## Providers

| Provider | Default model | Resume flag | Stream format | Auth |
|----------|---------------|-------------|----------------|------|
| Claude   | `sonnet` | `--resume <id>` | `--output-format stream-json` | `claude auth status --json` |
| Gemini   | `gemini-2.5-flash` | `--resume <id>` | `-o stream-json` | CLI check |
| Opencode | `opencode/gemini-3-flash` | `--session <id>` | `--format=json` | `opencode providers list` |

## Feature Matrix

| Feature | Claude | Gemini | Opencode |
|---------|--------|--------|----------|
| MCP servers | `--mcp-config` at runtime | Config only | Config only |
| Approval modes | `--permission-mode` | `--approval-mode` / `--yolo` | Config `permission:` |
| Budget cap | `--max-budget-usd` | - | - |
| List sessions | - | `--list-sessions` | `opencode session list` |
| List models | - | - | `opencode models` |
| Stats | Per-invocation | Per-invocation | `opencode stats` |
| Auth status | `claude auth status --json` | - | `opencode providers list` |