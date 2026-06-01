# agentpipe — agent onboarding

Async Python wrapper for coding-agent CLIs (Claude Code, Gemini, Opencode). Own repo under `agents/`.

## Quick start

```bash
uv add agentpipe
```

Provider CLIs (`claude`, `gemini`, `opencode`) must be installed and authenticated separately.

## Architecture

| Layer | File | Responsibility |
|-------|------|----------------|
| Public API | `agentpipe/__init__.py` | Exports `Agent`, `AgentSession`, pipeline fns, types |
| Agent facade | `agentpipe/_agent.py` | `Agent` dataclass — resolves provider, creates sessions |
| Session | `agentpipe/_session.py` | `AgentSession` — async context manager, manages resume IDs |
| Executor | `agentpipe/_executor.py` | `AsyncSubprocessExecutor` — runs CLI subprocesses, streaming |
| Types | `agentpipe/_types.py` | Frozen dataclasses for events, results, command specs |
| Pipeline | `agentpipe/_pipeline.py` | `fan_out`, `delegate`, `retry_until`, `map_concurrent` |
| Provider base | `agentpipe/providers/_base.py` | `Provider` Protocol — shape every provider implements |
| Claude | `agentpipe/providers/claude.py` | `ClaudeProvider` — `claude` CLI, stream-json format |
| Gemini | `agentpipe/providers/gemini.py` | `GeminiProvider` — `gemini` CLI, stream-json format |
| Opencode | `agentpipe/providers/opencode.py` | `OpencodeProvider` — `opencode run` CLI, JSON format |

## Usage patterns

- **One-shot:** `await Agent("claude").generate("prompt")` — creates session, runs, tears down.
- **Multi-turn:** `async with agent.session(cwd=".") as s: r1 = await s.generate("...")` — auto-resumes via `--resume <id>` on subsequent calls.
- **Streaming:** `async for event in agent.generate_stream("..."):` yields `ThinkingEvent | ToolCallEvent | ToolResultEvent | UsageEvent`.
- **Delegation:** `await delegate(draft_agent, review_agent, "write", "review")` — draft then review.
- **Fan-out:** `await fan_out(agent, ["prompt A", "prompt B"])` — semaphore-capped concurrency.

## Key conventions

- `master` branch (no `dev` — single-commit repo). Follows [[gh-automations-conventions]] for release flow when a remote is added.
- `pyproject.toml` at root — hatchling build, ruff lint (select `E,F,W,I,UP,…`), pytest + pytest-asyncio.
- Tests in `tests/unit/` — mock the executor layer; no live CLI calls.
- Use `tests/unit/providers/` for provider-specific tests once added.
