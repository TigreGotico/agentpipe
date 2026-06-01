# agentpipe

Async Python wrapper for coding agent CLIs (Claude Code, Gemini, Opencode).

## Install

```bash
uv add agentpipe
```

You still need the provider CLI installed and authenticated (`claude`, `gemini`, `opencode`).

## Quick Start

```python
from agentpipe import Agent

agent = Agent("claude", model="sonnet")

# One-shot
result = await agent.generate("Summarize this repo", cwd=".")
print(result)

# Multi-turn session with auto-resume
async with agent.session(cwd=".") as sess:
    r1 = await sess.generate("List key modules")
    r2 = await sess.generate("Which is riskiest?")

# Streaming events
async for event in agent.generate_stream("Explain architecture"):
    print(event)

# Simple delegation
from agentpipe import delegate
cheap = Agent("gemini", model="flash")
expensive = Agent("claude", model="sonnet")
final = await delegate(cheap, expensive, "Write tests", "Review for correctness")

# Fan-out
from agentpipe import fan_out
results = await fan_out(cheap, ["prompt A", "prompt B", "prompt C"])
```

## Providers

| Provider | Binary | Resume flag | Stream format |
|----------|--------|-------------|---------------|
| Claude   | `claude` | `--resume <id>` | `--output-format stream-json` |
| Gemini   | `gemini` | `--resume <id>` | `-o stream-json` |
| Opencode | `opencode` | `--session <id>` | `--format=json` |