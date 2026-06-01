# Getting Started

## Installation

```bash
uv add agentpipe
```

Or with pip:

```bash
pip install agentpipe
```

No Python runtime dependencies — agentpipe uses only `asyncio`, `dataclasses`, `json`, `re`, and `subprocess` from the standard library.

## Prerequisites

The provider CLIs must be installed and authenticated separately:

| CLI | Install | Auth |
|-----|---------|------|
| `claude` | `npm install -g @anthropics/claude-code` | `claude auth login` |
| `gemini` | `npm install -g @anthropic-ai/gemini-cli` | Browser-based OAuth |
| `opencode` | `npm install -g opencode` | `opencode auth` |

## 30-Second Quickstart

```python
import asyncio
from agentpipe import Agent

async def main():
    # Simplest usage — default free-tier model
    agent = Agent("gemini")  # → gemini-2.5-flash
    result = await agent.generate("Explain async/await in Python")
    print(result)

asyncio.run(main())
```

No configuration files, no API keys in code — agentpipe shells out to the installed CLIs.

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

## Next Steps

- **[Providers and Models](providers.md)** — See all provider aliases and model options
- **[Core API](core-api.md)** — Deep dive into Agent, sessions, events
- **[Model Cascade](cascade.md)** — Full cascade system documentation