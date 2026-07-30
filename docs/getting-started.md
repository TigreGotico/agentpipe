# Getting Started

## Installation

```bash
uv add agentpipe
```

Or with pip:

```bash
pip install agentpipe
```

agentpipe has no Python runtime dependencies. It uses only `asyncio`, `dataclasses`, `json`, `re`, and `subprocess` from the standard library.

## Prerequisites

The provider CLIs must be installed and authenticated separately:

| CLI | Install | Auth |
|-----|---------|------|
| `aider` | `pip install aider-chat` | OpenRouter OAuth (auto on first run) |
| `claude` | `npm install -g @anthropics/claude-code` | `claude auth login` |
| `gemini` | `npm install -g @anthropic-ai/gemini-cli` | Browser-based OAuth |
| `kilo` | `npm install -g @kilocode/cli` | `kilo auth login` (free tier: no CC) |
| `opencode` | `npm install -g opencode` | `opencode auth` |
| `vibe` | `pip install mistral-vibe` | `vibe --setup` (Mistral API key) |

## 30-Second Quickstart

```python
import asyncio
from agentpipe import Agent

async def main():
    # simplest usage: default free-tier model
    agent = Agent("gemini")  # → gemini-2.5-flash
    result = await agent.generate("Explain async/await in Python")
    print(result)

asyncio.run(main())
```

agentpipe has no configuration files and no API keys in code. It shells out to the installed CLIs.

For the full result with usage tracking:

```python
result = await agent.generate_full("Explain async/await in Python")
print(result.text)         # the response text
print(result.usage)        # UsageEvent or None
print(result.session_id)   # session ID for resuming
```

## Streaming

```python
async for event in agent.generate_stream("Explain architecture"):
    match event:
        case ThinkingEvent(text=t):     print(t, end="")
        case ToolCallEvent(tool=name):  print(f"[tool: {name}]")
        case ToolResultEvent(tool=name, output=out): print(f"[{name}: {out[:50]}]")
        case UsageEvent(input_tokens=n): print(f"Tokens: {n}")
```

## Multi-Turn Sessions

```python
async with agent.session(cwd=".") as sess:
    r1 = await sess.generate("List key modules")
    r2 = await sess.generate("Which is riskiest?")  # auto-resumes

    print(sess.session_id)                # e.g. "sess-abc123"
    print(sess.usage.total_input_tokens)  # accumulated across turns
    print(sess.usage.total_cost_usd)
    print(sess.usage.turn_count)          # number of generate() calls
```

## All Provider Features

agentpipe exposes the full CLI feature set across all providers:

```python
from agentpipe import Agent, ApprovalMode, EffortLevel

# System prompt (Claude, Qoder)
agent = Agent("claude", system_prompt="You are a code reviewer")

# Approval modes (Claude, Gemini, OpenCode, Kilo, Vibe)
agent = Agent("gemini", approval_mode=ApprovalMode.YOLO)

# Effort level (Claude, OpenCode/Kilo as "variant", Aider as "reasoning-effort")
agent = Agent("claude", effort=EffortLevel.HIGH)

# Sandbox mode (Claude, Gemini, OpenCode, Kilo)
agent = Agent("opencode", sandbox=True)

# File attachments (Aider, Claude, OpenCode, Kilo)
agent = Agent("claude", files=["README.md", "src/main.py"])

# Continue last session (Claude, OpenCode, Kilo)
agent = Agent("claude", continue_last=True)

# Agent selection (Claude, OpenCode, Kilo, Vibe)
agent = Agent("opencode", agent_name="reviewer")

# Extensions (Gemini)
agent = Agent("gemini", extensions=["search", "code"])

# Include additional directories (all providers)
agent = Agent("claude", include_dirs=["/src", "/lib"])

# Show thinking blocks (Kilo)
agent = Agent("kilo", show_thinking=True)
```

## Model Cascade (Failover)

```python
from agentpipe import cascade

# Start free, escalate on failure
result = await cascade("Write tests for this function")

# Only free models, zero cost
result = await cascade("Quick question", profile="free-only")

# From the CLI
# python -m agentpipe.cascade_run --free-only "Quick question"
```

## HTTP Server (FastAPI)

Run agents behind HTTP with an OpenAI-compatible endpoint:

```bash
pip install agentpipe fastapi uvicorn sse-starlette
python -m agentpipe.server
```

```bash
# OpenAI-compatible: works with any OpenAI client
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"kilo/kilo-auto/free","messages":[{"role":"user","content":"Write tests"}]}'
```

See the [HTTP Server docs](server.md) for the full API reference and Docker setup.

## Next Steps

- **[Providers and Models](providers.md)** - all provider aliases and model options
- **[Core API](core-api.md)** - Agent, sessions, events, results
- **[Model Cascade](cascade.md)** - full cascade system documentation
- **[HTTP Server](server.md)** - multi-agent HTTP API with OpenAI-compatible endpoint
- **[MCP and Approval Modes](mcp-approval.md)** - MCP servers, approval modes, budget caps
- **[Auth and Quota](auth-quota.md)** - auth, quota, session management, MCP management
- **[Feature Matrix](feature-matrix.md)** - per-provider feature comparison

---
[Home](index.md) · [Providers and Models →](providers.md)