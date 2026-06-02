# agentpipe

[![PyPI version](https://img.shields.io/pypi/v/agentpipe?color=blue)](https://pypi.org/project/agentpipe/)
[![Python versions](https://img.shields.io/pypi/pyversions/agentpipe)](https://pypi.org/project/agentpipe/)
[![License](https://img.shields.io/github/license/TigreGotico/agentpipe)](LICENSE)
[![CI](https://github.com/TigreGotico/agentpipe/actions/workflows/build-tests.yml/badge.svg?branch=dev)](https://github.com/TigreGotico/agentpipe/actions)
[![DeepWiki](https://deepwiki.com/badge/TigreGotico/agentpipe)](https://deepwiki.com/repo/TigreGotico/agentpipe)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://github.com/TigreGotico/agentpipe/pkgs/container/agentpipe)

**Let your expensive coding agent delegate the boring work to cheap ones.**

agentpipe gives you a single async Python API over 7 coding agent CLIs (Aider,
Claude Code, Gemini CLI, Kilo Code, OpenCode, QoderCLI, Vibe). Use it to build
multi-agent pipelines where a smart planner delegates tasks to cheaper workers.

```python
from agentpipe import Agent, delegate, fan_out

# Plan with Claude, delegate execution to free models
async def build_feature():
    draft = await Agent("opencode-free").generate("Write a CLI arg parser")
    review = await Agent("claude-sonnet").generate(f"Review this:\n{draft}")
    return review

# Or use the built-in delegation pipeline
result = await delegate(
    Agent("opencode-free"),  # drafter — cheap
    Agent("claude-sonnet"),  # reviewer — smart
    "Write a palindrome checker",
    "Review for edge cases",
)
```

Zero Python dependencies. Works with Python 3.10+.

## Why?

Coding agents are powerful but expensive. Claude Opus costs ~$15/M tokens.
Opencode-free models cost $0. The smartest approach: let a strong agent plan
and review, but delegate grunt work (linting, boilerplate, test writing) to
free-tier agents.

agentpipe wraps every major coding agent CLI behind the same async interface
so you can mix and match them in a single script.

## Quick Start

```bash
pip install agentpipe
```

Pick any provider you have installed:

```python
import asyncio
from agentpipe import Agent

async def main():
    # One-shot with a free model
    result = await Agent("kilo").generate("Explain async/await")
    print(result)

    # Multi-turn session with cost tracking
    async with Agent("gemini-flash").session(cwd=".") as sess:
        r1 = await sess.generate("List the modules")
        r2 = await sess.generate("Which is riskiest?")
        print(f"Cost: ${sess.usage.total_cost_usd:.4f}")

    # Stream events as they happen
    async for event in Agent("aider").generate_stream("Explain this code"):
        match event:
            case ThinkingEvent(text=t): print(t, end="")
            case UsageEvent(input_tokens=n): print(f"\n[Tokens: {n}]")

asyncio.run(main())
```

## Delegate: Draft + Review

The killer feature. Use a cheap/free agent to write, then a strong agent to review.

```python
from agentpipe import delegate

final = await delegate(
    Agent("kilo"),          # drafter — free
    Agent("claude-sonnet"), # reviewer — smart
    "Write a unit test for this class",
    "Check correctness, coverage, and style",
)
```

## Fan-Out: Parallel subtasks

```python
from agentpipe import fan_out, Agent

results = await fan_out(
    Agent("aider", timeout=60),
    ["Write tests for module A", "Write tests for module B"],
    max_concurrency=3,
)
```

## Cascade: Automatic fallback

Try free models first, escalate to paid on failure, with cost caps.

```python
from agentpipe import cascade

# Start free, escalate on failure
result = await cascade("Write tests", profile="default")

# Cap cost at $0.10
result = await cascade("Refactor", max_cost_usd=0.10)

# Only free models
result = await cascade("Quick question", profile="free-only")
```

## All Providers

| Provider | Key | Default Model | Cost |
|----------|-----|---------------|------|
| Aider | `aider` | `openrouter/...gemma-4:free` | Free (OpenRouter) |
| Claude Code | `claude` | `sonnet` | $10-200/mo sub |
| Gemini CLI | `gemini` | `gemini-2.5-flash` | Free tier |
| Kilo Code | `kilo` | `kilo/kilo-auto/free` | Free tier |
| OpenCode Free | `opencode-free` | `opencode/big-pickle` | $0 |
| OpenCode Zen | `opencode-zen` | `opencode/gemini-3-flash` | Pay-as-you-go |
| OpenCode Go | `opencode-go` | `opencode-go/deepseek-v4-flash` | $5-10/mo |
| QoderCLI | `qoder` | *(CLI default)* | Per-use |
| Mistral Vibe | `vibe` | `mistral-large-latest` | Free tier |

## Install Provider CLIs

```
# Aider (free — OpenRouter)
pip install aider-chat

# Claude Code (paid subscription)
npm install -g @anthropics/claude-code

# Gemini CLI (free — Google account)
npm install -g @google-gemini/gemini-cli

# Kilo Code (free — no CC needed)
npm install -g @kilocode/cli

# OpenCode (free tier available)
npm install -g opencode

# Mistral Vibe (free tier)
pip install mistral-vibe
```

## HTTP Server (FastAPI)

Run multiple agents behind HTTP with persistent sessions — perfect for CI/CD,
other agents to call, or multi-process deployments.

Includes an **OpenAI-compatible `/v1/chat/completions` endpoint** so any
OpenAI client (Cursor, Continue.dev, etc.) can be pointed at this server.

```bash
pip install agentpipe fastapi uvicorn sse-starlette
python -m agentpipe.server
```

```bash
# OpenAI-compatible — works with any OpenAI SDK
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"kilo/kilo-auto/free","messages":[{"role":"user","content":"Write tests"}]}'

# The model prefix selects the provider:
#   kilo/... → Kilo Code (free)    claude/... → Claude Code
#   gemini/... → Gemini CLI        opencode/... → OpenCode
#   aider/... → Aider              vibe/... → Mistral Vibe

# Native API — create named agents with persistent sessions
curl -X POST http://localhost:8000/agents \
  -H 'Content-Type: application/json' \
  -d '{"name":"writer","provider":"kilo"}'

# Send work — sessions persist automatically
curl -X POST http://localhost:8000/agents/writer/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Write unit tests for src/parser.py"}'

# Stream events via SSE
curl -X POST http://localhost:8000/agents/writer/generate-stream \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Explain this code"}'

# Check session status
curl http://localhost:8000/agents/writer/session
```

### Docker

The image is auto-built on every push to `dev` and published to
`ghcr.io/tigregotico/agentpipe:latest`.

```bash
# Pull the published image
docker compose up

# Or build locally
docker compose build

# Pass API keys
# OPENROUTER_API_KEY=sk-xxx docker compose up
```

See the [server module](agentpipe/server.py) for the full API.

## Docs

- [Getting Started](docs/getting-started.md) — Install, quickstart, all features
- [Providers and Models](docs/providers.md) — Aliases, defaults, OpenCode plans
- [Core API](docs/core-api.md) — Agent, sessions, events
- [Pipeline Functions](docs/pipelines.md) — fan_out, delegate, retry_until
- [Model Cascade](docs/cascade.md) — Fallback, cost caps, profiles
- [Feature Matrix](docs/feature-matrix.md) — Per-provider comparison
- [API Reference](docs/api-reference.md) — All exports

## 25 Example Scripts

```bash
python -m examples.20_fastapi_integration  # HTTP server
python -m examples.11_delegate             # Draft + review pipeline
python -m examples.10_fan_out              # Parallel subtasks
python -m examples.07_cascade              # Free → paid fallback
python -m examples.01_one_shot             # Simplest usage
```

## License

MIT
