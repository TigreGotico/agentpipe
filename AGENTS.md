# agentpipe — agent onboarding

Async Python wrapper for coding-agent CLIs (Aider, Claude Code, Gemini, Kilo Code, OpenCode, QoderCLI, Vibe). Own repo under `agents/`.

## Quick start

```bash
uv add agentpipe
```

Provider CLIs must be installed and authenticated separately (see README).

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
| Aider | `agentpipe/providers/aider.py` | `AiderProvider` — `aider` CLI, plain text / tokens |
| Claude | `agentpipe/providers/claude.py` | `ClaudeProvider` — `claude` CLI, stream-json format |
| Gemini | `agentpipe/providers/gemini.py` | `GeminiProvider` — `gemini` CLI, stream-json format |
| Kilo | `agentpipe/providers/kilo.py` | `KiloProvider` — `kilo` CLI, JSON format |
| OpenCode | `agentpipe/providers/opencode.py` | `OpencodeProvider` — `opencode run` CLI, JSON format |
| QoderCLI | `agentpipe/providers/qoder.py` | `QoderProvider` — `qodercli` CLI, stream-json format |
| Vibe | `agentpipe/providers/vibe.py` | `VibeProvider` — `vibe` CLI, NDJSON streaming format |

## Usage patterns

- **One-shot:** `await Agent("claude").generate("prompt")` — creates session, runs, tears down.
- **Multi-turn:** `async with agent.session(cwd=".") as s: r1 = await s.generate("...")` — auto-resumes via `--resume <id>` on subsequent calls.
- **Streaming:** `async for event in agent.generate_stream("..."):` yields `ThinkingEvent | ToolCallEvent | ToolResultEvent | UsageEvent`.
- **Delegation:** `await delegate(draft_agent, review_agent, "write", "review")` — draft then review.
- **Fan-out:** `await fan_out(agent, ["prompt A", "prompt B"])` — semaphore-capped concurrency.

## CI

Full gh-automations CI set present (10 workflows). Pinned at `@dev`.

## Conventions (org hard rules)

- Branches: work on `dev`, stable on `master`; `dev` is the GitHub default. Never `main`.
- Never edit `agentpipe/version.py`; gh-automations bumps semver from conventional-commit prefixes.
- New repos are private by default.
- Commit identity: JarbasAi <jarbasai@mailfence.com>.
- Reference `OpenVoiceOS/gh-automations` reusable workflows at `@dev`.
- No Neon / `neon-*` references. No meta-commentary in code/docs/commits/PRs.
- Tests in `tests/` — mock the executor layer; no live CLI calls.

## Setup on GitHub

- Set `PYPI_TOKEN` as a repo secret for automated publishing.
- Set `dev` as the default branch (repo Settings → Branches).
