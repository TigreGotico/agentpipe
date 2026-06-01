# agentpipe

Async Python wrapper for coding agent CLIs (Claude Code, Gemini, Opencode). Zero dependencies. Python 3.10+.

**[Full documentation →](docs/index.md)**

## Install

```bash
uv add agentpipe
```

Provider CLIs (`claude`, `gemini`, `opencode`) must be installed and authenticated separately.

## Quick Start

```python
from agentpipe import Agent

# One-shot with default free-tier model
result = await Agent("gemini").generate("Explain async/await")
print(result)

# Multi-turn session with usage tracking
async with Agent("claude-sonnet").session(cwd=".") as sess:
    r1 = await sess.generate("List key modules")
    r2 = await sess.generate("Which is riskiest?")  # auto-resumes
    print(sess.usage.total_cost_usd)

# Streaming events
async for event in Agent("opencode-free").generate_stream("Explain architecture"):
    match event:
        case ThinkingEvent(text=t):    print(t, end="")
        case ToolCallEvent(tool=name): print(f"[tool: {name}]")
        case UsageEvent(input_tokens=n): print(f"Tokens: {n}")
```

## Provider Aliases

```python
Agent("claude")           # sonnet
Agent("claude-sonnet")    # sonnet
Agent("claude-haiku")     # haiku
Agent("claude-opus")      # opus
Agent("gemini-flash")     # gemini-2.5-flash
Agent("gemini-pro")       # gemini-2.5-pro
Agent("opencode-free")    # opencode/big-pickle      ($0)
Agent("opencode-zen")     # opencode/gemini-3-flash   (pay-per-token)
Agent("opencode-go")      # opencode-go/deepseek-v4-flash  (subscription)
```

## Model Cascade (Fallback)

```python
from agentpipe import cascade, ModelTier

# Start free, escalate on failure
result = await cascade("Write tests", profile="default")

# Only free models
result = await cascade("Quick question", profile="free-only")

# Cap cost and tier
result = await cascade("Refactor", max_tier=ModelTier.CHEAP, max_cost_usd=0.50)

# CLI
# python -m agentpipe.cascade_run --profile coding --max-tier cheap "Write tests"
```

## Pipeline Functions

```python
from agentpipe import Agent, fan_out, delegate, retry_until, map_concurrent

# Fan-out: one agent, multiple prompts
results = await fan_out(Agent("gemini"), ["prompt A", "prompt B"])

# Delegate: draft then review
final = await delegate(Agent("opencode-free"), Agent("claude-sonnet"), "Write", "Review")

# Retry until validator passes
result = await retry_until(Agent("gemini"), "Fix", validator=lambda r: "ok" in r)

# Same prompt, multiple agents
results = await map_concurrent([Agent("claude"), Agent("gemini")], "Explain")
```

## Feature Matrix

| Feature | Claude | Gemini | Opencode |
|---------|--------|--------|----------|
| MCP servers | Yes (`--mcp-config`) | Config only | Config only |
| Approval modes | Yes | Yes | Config only |
| Budget cap | Yes | — | — |
| Session resume | `--resume` | `--resume` | `--session` |
| Auth status | Yes | Limited | Yes |
| Model listing | — | — | Yes |
| Plan variants | Sonnet/Haiku/Opus | Flash/Pro | Free/Zen/Go |