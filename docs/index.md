# agentpipe — Documentation

> Async Python wrapper for coding agent CLIs. Zero dependencies. Python 3.10+.

---

## Table of Contents

1. [Installation](#installation)
2. [30-Second Quickstart](#30-second-quickstart)
3. [Providers and Models](#providers-and-models)
   - [Provider Aliases (Flagship Models)](#provider-aliases-flagship-models)
   - [OpenCode Plans: Free / Zen / Go](#opencode-plans-free--zen--go)
   - [Model Tier Map](#model-tier-map)
4. [Core API](#core-api)
   - [Agent Dataclass](#agent-dataclass)
   - [Generation Methods](#generation-methods)
   - [Multi-Turn Sessions](#multi-turn-sessions)
   - [Event Types](#event-types)
   - [GenerationResult](#generationresult)
5. [Pipeline Functions](#pipeline-functions)
   - [fan_out](#fan_out)
   - [delegate](#delegate)
   - [retry_until](#retry_until)
   - [map_concurrent](#map_concurrent)
6. [Model Cascade (Fallback)](#model-cascade-fallback)
   - [cascade()](#cascade)
   - [Cascade Profiles](#cascade-profiles)
   - [Tiers and Cost Control](#tiers-and-cost-control)
   - [Convenience Functions](#convenience-convenience-functions)
   - [CLI Runner](#cli-runner)
7. [MCP Server Configuration](#mcp-server-configuration)
8. [Approval Modes and Budget Caps](#approval-modes-and-budget-caps)
9. [Auth, Quota, and Rate Limits](#auth-quota-and-rate-limits)
10. [Session Management](#session-management)
11. [Provider Internals](#provider-internals)
   - [The Provider Protocol](#the-provider-protocol)
   - [Provider Classes](#provider-classes)
   - [Command Building](#command-building)
   - [Event Parsing](#event-parsing)
12. [Advanced Usage](#advanced-usage)
    - [Custom Executors](#custom-executors)
    - [Error Handling](#error-handling)
    - [Integrating with Other Frameworks](#integrating-with-other-frameworks)
13. [Feature Matrix](#feature-matrix)
14. [API Reference](#api-reference)

---

## Installation

```bash
uv add agentpipe
```

Or with pip:

```bash
pip install agentpipe
```

**Prerequisites:** The provider CLIs must be installed and authenticated separately:

| CLI | Install | Auth |
|-----|---------|------|
| `claude` | `npm install -g @anthropics/claude-code` | `claude auth login` |
| `gemini` | `npm install -g @anthropic-ai/gemini-cli` | Browser-based OAuth |
| `opencode` | `npm install -g opencode` | `opencode auth` |

No Python runtime dependencies. agentpipe uses only the standard library (`asyncio`, `dataclasses`, `json`, `re`, `subprocess`).

---

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

That's it. No configuration files, no API keys in code — agentpipe shells out to the installed CLIs.

For the full result with usage tracking:

```python
result = await agent.generate_full("Explain async/await in Python")
print(result.text)             # the response text
print(result.usage)            # UsageEvent or None
print(result.session_id)       # session ID for resuming
```

---

## Providers and Models

### Provider Aliases (Flagship Models)

Each provider has shortcuts that pre-fill the default model for a particular tier:

```python
from agentpipe import Agent

# Claude family
Agent("claude")           # model="sonnet"    (ClaudeProvider)
Agent("claude-sonnet")    # model="sonnet"    (ClaudeSonnetProvider)
Agent("claude-haiku")     # model="haiku"    (ClaudeHaikuProvider)
Agent("claude-opus")      # model="opus"     (ClaudeOpusProvider)

# Gemini family
Agent("gemini")           # model="gemini-2.5-flash"  (GeminiProvider)
Agent("gemini-flash")     # model="gemini-2.5-flash"  (GeminiFlashProvider)
Agent("gemini-pro")       # model="gemini-2.5-pro"   (GeminiProProvider)

# OpenCode family — three plans
Agent("opencode")         # model="opencode/gemini-3-flash"  (OpencodeZenProvider)
Agent("opencode-free")    # model="opencode/big-pickle"      (OpencodeFreeProvider)
Agent("opencode-zen")     # model="opencode/gemini-3-flash"  (OpencodeZenProvider)
Agent("opencode-go")      # model="opencode-go/deepseek-v4-flash" (OpencodeGoProvider)
```

You can always override the model:

```python
Agent("claude", model="opus")
Agent("opencode-go", model="opencode-go/kimi-k2.6")
```

### OpenCode Plans: Free / Zen / Go

OpenCode has three distinct plans that use different API endpoints, billing, and rate limits:

| Plan | Provider | Endpoint | Billing | Default Model |
|------|----------|----------|---------|---------------|
| **Free** | `opencode-free` | `opencode.ai/zen/v1` | $0 — free models only | `opencode/big-pickle` |
| **Zen** | `opencode-zen` | `opencode.ai/zen/v1` | Pay-as-you-go | `opencode/gemini-3-flash` |
| **Go** | `opencode-go` | `opencode.ai/zen/go/v1` | $5/$10 monthly subscription | `opencode-go/deepseek-v4-flash` |

Key differences:

- **Free** and **Zen** share the same API endpoint and API key. Free models (`big-pickle`, `gemini-3-flash`, `*-free` suffixes) cost $0; all other Zen models charge per token.
- **Go** is a separate subscription with its own endpoint, rate limits (per-model per 5 hours), and flat monthly billing.
- The model prefix (`opencode/` vs `opencode-go/`) determines which endpoint is hit. Free and Zen both use `opencode/` prefix models; Go uses `opencode-go/` prefix.
- All three use the same `opencode` binary — the model string routes the request.

```python
# Free: $0 cost, limited models
agent = Agent("opencode-free")   # → big-pickle

# Zen: pay-as-you-go, full model catalog
agent = Agent("opencode-zen")    # → gemini-3-flash

# Go: subscription, higher rate limits
agent = Agent("opencode-go")     # → deepseek-v4-flash (Go endpoint)
```

The cascade system automatically routes models to the correct plan — models in `_FREE_MODELS` go to `opencode-free`, `opencode-go/` prefixed models go to `opencode-go`, and all other `opencode/` models go to `opencode-zen`.

### Model Tier Map

The cascade system classifies models into cost tiers:

| Tier | Value | Models |
|------|-------|--------|
| **FREE** | 0 | `opencode/big-pickle`, `gemini-2.5-flash`, `opencode/gemini-3-flash`, `opencode/deepseek-v4-flash-free`, `opencode/mimo-v2.5-free`, `opencode/nemotron-3-super-free`, `opencode/minimax-m3-free` |
| **CHEAP** | 1 | `opencode/kimi-k2.5`, `opencode/minimax-m2.5`, `opencode-go/deepseek-v4-flash` |
| **MID** | 2 | `opencode/kimi-k2.6`, `opencode/minimax-m2.7`, `opencode/glm-5`, `opencode/glm-5.1`, `opencode-go/glm-5.1` |
| **PREMIUM** | 3 | `opencode/gpt-5`, `opencode/qwen3.6-plus`, `opencode/qwen3.5-plus`, `opencode/gemini-3.1-pro` |

Models not in the map default to `MID`.

---

## Core API

### Agent Dataclass

```python
from agentpipe import Agent, ApprovalMode, HttpMcpServer

agent = Agent(
    provider="claude-sonnet",      # str — provider name or alias
    model=None,                    # str | None — model override (filled from DEFAULT_MODELS if None)
    cwd="/tmp",                    # str — working directory for subprocesses
    timeout=300,                   # int — seconds before killing the subprocess
    mcp_servers=[],               # list[McpServerConfig] — Claude MCP servers
    approval_mode=None,            # ApprovalMode | None — Claude permission mode
    max_budget_usd=None,          # float | None — Claude budget cap
)
```

`Agent` is a plain `@dataclass` with a `__post_init__` that resolves the default model and validates the provider name. The `_provider_instance` attribute is set from the provider map and is used internally.

**Provider map** (what `Agent("name")` resolves to):

| Name | Class | Default Model |
|------|-------|---------------|
| `claude` | `ClaudeProvider` | `sonnet` |
| `claude-sonnet` | `ClaudeSonnetProvider` | `sonnet` |
| `claude-haiku` | `ClaudeHaikuProvider` | `haiku` |
| `claude-opus` | `ClaudeOpusProvider` | `opus` |
| `gemini` | `GeminiProvider` | `gemini-2.5-flash` |
| `gemini-flash` | `GeminiFlashProvider` | `gemini-2.5-flash` |
| `gemini-pro` | `GeminiProProvider` | `gemini-2.5-pro` |
| `opencode` | `OpencodeZenProvider` | `opencode/gemini-3-flash` |
| `opencode-free` | `OpencodeFreeProvider` | `opencode/big-pickle` |
| `opencode-zen` | `OpencodeZenProvider` | `opencode/gemini-3-flash` |
| `opencode-go` | `OpencodeGoProvider` | `opencode-go/deepseek-v4-flash` |

### Generation Methods

All generation methods are `async`. agentpipe spawns one subprocess per call — no persistent daemon.

```python
# Returns just the text
text: str = await agent.generate("Explain this function")

# Returns structured result with events, usage, session_id
result: GenerationResult = await agent.generate_full("Refactor this module")

# Yields streaming events
async for event in agent.generate_stream("Explain architecture"):
    match event:
        case ThinkingEvent(text=t):    print(t, end="")
        case ToolCallEvent(tool=name): print(f"[tool: {name}]")
        case ToolResultEvent(tool=name, output=out): print(f"[{name}: {out[:50]}]")
        case UsageEvent(input_tokens=n): print(f"Tokens: {n}")
```

All three accept `cwd` and `timeout` overrides:

```python
result = await agent.generate("prompt", cwd="/home/user/project", timeout=120)
```

### Multi-Turn Sessions

Sessions auto-resume: the first call has no `--resume` flag, and subsequent calls include `--resume <session_id>`.

```python
async with agent.session(cwd=".") as sess:
    r1 = await sess.generate("List key modules")
    r2 = await sess.generate("Which is riskiest?")  # auto-resumes

    print(sess.session_id)                    # e.g. "sess-abc123"
    print(sess.usage.total_input_tokens)      # accumulated across turns
    print(sess.usage.total_output_tokens)
    print(sess.usage.total_cost_usd)
    print(sess.usage.turn_count)             # number of generate() calls
```

`AgentSession` is an async context manager (`async with`). Usage accumulates across turns via `SessionUsage`.

### Event Types

All events are frozen dataclasses. `AgentEvent` is a union type.

```python
from agentpipe import ThinkingEvent, ToolCallEvent, ToolResultEvent, UsageEvent

# ThinkingEvent(text: str)
#   — Model text output

# ToolCallEvent(tool: str, args: dict | str | None = None, tool_id: str | None = None)
#   — Tool invocation start

# ToolResultEvent(tool: str, output: str = "", exit_code: int | None = None, duration_ms: float | None = None)
#   — Tool execution result

# UsageEvent(input_tokens: int = 0, output_tokens: int = 0, cost_usd: float | None = None,
#            cache_read_tokens: int = 0, cache_write_tokens: int = 0)
#   — Per-step token usage and cost
```

### GenerationResult

```python
from agentpipe import GenerationResult

result = GenerationResult(
    text="The answer is 42",           # str — extracted text
    events=(),                          # tuple[AgentEvent, ...] — all parsed events
    session_id="sess-abc123",           # str | None
    usage=UsageEvent(...),              # UsageEvent | None
    returncode=0,                       # int
)
```

---

## Pipeline Functions

### fan_out

Run multiple prompts through the same agent concurrently (semaphore-capped):

```python
from agentpipe import Agent, fan_out

agent = Agent("gemini")
results: list[str] = await fan_out(
    agent,
    ["Summarize file A", "Summarize file B", "Summarize file C"],
    max_concurrency=3,  # semaphore limit
    cwd=".",
    timeout=120,
)
# results = ["summary of A", "summary of B", "summary of C"]
```

### delegate

Draft with one agent, review with another:

```python
from agentpipe import Agent, delegate

drafter = Agent("opencode-free")   # cheap/fast for drafting
reviewer = Agent("claude-sonnet")  # strong for review

final: str = await delegate(
    drafter,
    reviewer,
    "Write a unit test for this function",
    "Review for correctness and edge cases",  # optional, defaults to review prompt
)
```

The reviewer receives the drafter's output prepended to the review prompt.

### retry_until

Keep retrying until a validator function passes:

```python
from agentpipe import Agent, retry_until

agent = Agent("opencode-zen")
result: str = await retry_until(
    agent,
    "Fix all lint errors in this file",
    validator=lambda text: "no errors" in text.lower(),
    max_attempts=3,
    refine_prompt="The result still has errors. Fix them.",
)
```

If `refine_prompt` is provided, subsequent attempts prepend the previous output + refine prompt. Otherwise, the original prompt is retried.

### map_concurrent

Send the same prompt to multiple agents concurrently:

```python
from agentpipe import Agent, map_concurrent

agents = [Agent("claude-sonnet"), Agent("gemini-pro"), Agent("opencode-zen")]
results: list[str] = await map_concurrent(agents, "Explain quantum computing in one paragraph")
# One response per agent
```

---

## Model Cascade (Fallback)

The cascade system tries models in priority order, automatically falling back when a model is rate-limited, errors out, or times out.

### cascade()

```python
from agentpipe import cascade, CascadeResult

result: CascadeResult = await cascade(
    "Write a fast sorting algorithm",
    # Pick ONE of: models= or profile= (models overrides profile)
    models=["opencode/big-pickle", "gemini-2.5-flash", "opencode/kimi-k2.5"],
    profile="default",           # named profile from CASCADE_PROFILES
    max_tier=None,               # ModelTier — stop escalating beyond this tier
    max_attempts=10,             # max models to try
    max_cost_usd=None,           # stop if cumulative cost exceeds this
    max_total_seconds=None,      # stop if wall time exceeds this
    per_attempt_timeout=120,     # seconds per model call
    retry_delay_seconds=2.0,     # pause between failed attempts
    rate_limit_backoff_seconds=10, # pause after hitting a rate limit
    cwd="/tmp",                  # working directory
    on_attempt=None,             # callback(CascadeAttempt) called after each attempt
)
```

Returns a `CascadeResult`:

```python
result.text                   # str — output from the first successful model
result.successful_model       # str | None — e.g. "opencode/big-pickle"
result.successful_provider    # str | None — e.g. "opencode-free"
result.attempts               # list[CascadeAttempt] — full history
result.total_cost_usd         # float — cumulative cost
result.total_duration_seconds # float — wall time
result.attempt_count          # int
result.failed_attempts        # list[CascadeAttempt]
result.rate_limited_models     # list[str]
```

Each `CascadeAttempt`:

```python
attempt.model               # str — model name
attempt.provider             # str — resolved provider
attempt.success               # bool
attempt.error_type             # ErrorType | None — RATE_LIMIT, PROCESS_ERROR, TIMEOUT, UNKNOWN
attempt.error_message          # str | None
attempt.rate_limit_resets_in   # int | None — seconds until rate limit resets
attempt.cost_usd               # float | None
attempt.input_tokens           # int
attempt.output_tokens          # int
attempt.duration_seconds       # float
attempt.result_text             # str | None — output if success
```

Error handling: if all models fail, `cascade()` raises `RuntimeError` with a summary of which models were tried and what errors occurred.

### Cascade Profiles

Built-in profiles (ordered by priority):

| Profile | Strategy |
|---------|----------|
| `default` | Start free, escalate — big-pickle → gemini-flash → gemini-3-flash → deepseek-free → mimo-free → nemotron-free → kimi-k2.5 → minimax-m2.5 |
| `coding` | Coding-capable models first — big-pickle → deepseek-free → gemini-3-flash → gemini-2.5-flash → deepseek-v4-flash → kimi-k2.6 → go/deepseek-v4-flash → minimax-m2.7 |
| `reasoning` | Strong reasoners first — kimi-k2.6 → glm-5.1 → minimax-m2.7 → glm-5 → minimax-m2.5 → gemini-flash → big-pickle |
| `fast-free` | Quickly available free models — big-pickle → gemini-flash → gemini-3-flash → deepseek-free |
| `free-only` | Only zero-cost models — big-pickle → deepseek-free → gemini-3-flash → gemini-flash → mimo-free → nemotron-free |

### Tiers and Cost Control

```python
from agentpipe import cascade, ModelTier

# Only try FREE and CHEAP models
result = await cascade("prompt", max_tier=ModelTier.CHEAP)

# Only try FREE models (zero cost guaranteed)
result = await cascade("prompt", max_tier=ModelTier.FREE)

# Stop if cumulative cost exceeds $0.50
result = await cascade("prompt", max_cost_usd=0.50)

# Stop if wall time exceeds 60 seconds
result = await cascade("prompt", max_total_seconds=60)
```

Combining constraints:

```python
result = await cascade(
    "Quick question",
    profile="free-only",
    max_tier=ModelTier.FREE,
    max_cost_usd=0.01,        # effectively free
    max_attempts=3,            # don't try more than 3 models
    per_attempt_timeout=30,    # 30s per model
)
```

### Convenience Functions

```python
from agentpipe import cascade_coding, cascade_fast_free, cascade_free_only

# Coding-optimized, stops at CHEAP tier
result = await cascade_coding("Write tests for foo.py")

# Fast free models only
result = await cascade_fast_free("Quick question")

# All free models, no cost
result = await cascade_free_only("Explain this concept")
```

### CLI Runner

```bash
# Basic usage
python -m agentpipe.cascade_run "Write a unit test for this function"

# Choose a profile
python -m agentpipe.cascade_run --profile coding "Refactor this module"

# Explicit model list
python -m agentpipe.cascade_run --models "opencode/big-pickle,gemini-2.5-flash" "Summarize"

# Free models only
python -m agentpipe.cascade_run --free-only "Quick question"

# Tier cap and cost control
python -m agentpipe.cascade_run --max-tier cheap --max-cost 0.50 "Prompt"

# JSON output
python -m agentpipe.cascade_run --json "Explain this architecture"
```

---

## MCP Server Configuration

MCP (Model Context Protocol) servers are currently only supported for Claude.

```python
from agentpipe import Agent, HttpMcpServer, StdioMcpServer

agent = Agent("claude", mcp_servers=[
    # HTTP/SSE server
    HttpMcpServer(
        name="docs",
        url="http://localhost:9000/sse",
        headers={"Authorization": "Bearer tok"},
    ),
    # Stdio server
    StdioMcpServer(
        name="github",
        command="npx",
        args=["-y", "@mcp/server-github"],
        env={"GITHUB_TOKEN": "ghp_x"},
    ),
])

result = await agent.generate("Use the MCP tools to inspect the repo")
```

At build time, these are serialized to a `--mcp-config` JSON blob passed to the Claude CLI.

---

## Approval Modes and Budget Caps

Approval modes and budget caps are Claude-specific features.

```python
from agentpipe import Agent, ApprovalMode

# Full auto — uses --dangerously-skip-permissions (default for bypass/yolo)
agent = Agent("claude")  # default mode

# Plan mode (read-only, no tool execution)
agent = Agent("claude", approval_mode=ApprovalMode.PLAN)

# Auto-edit (auto-approve file edits, ask for shell commands)
agent = Agent("claude", approval_mode=ApprovalMode.AUTO_EDIT)

# Budget cap at $1.00
agent = Agent("claude", max_budget_usd=1.00)
```

| ApprovalMode | Claude CLI Flag |
|---|---|
| `DEFAULT` | `--dangerously-skip-permissions` |
| `AUTO_EDIT` | `--permission-mode acceptEdits` |
| `YOLO` | `--dangerously-skip-permissions` |
| `PLAN` | `--permission-mode plan` |
| `BYPASS` | `--dangerously-skip-permissions` |

---

## Auth, Quota, and Rate Limits

### check_quota

```python
from agentpipe import check_quota

# Check each provider
for provider in ["claude", "gemini", "opencode", "opencode-go"]:
    status = await check_quota(provider)
    print(f"{provider}:")
    print(f"  authenticated:  {status.authenticated}")
    print(f"  subscription:   {status.subscription_type}")
    print(f"  rate_limited:   {status.rate_limited}")
    print(f"  resets_in:      {status.rate_limit_resets_in_seconds}s")
    print(f"  models:         {len(status.available_models)}")
    print(f"  usage_stats:    {status.usage_stats}")
```

Returns a `QuotaStatus` with fields: `authenticated`, `subscription_type`, `email`, `plan_limits`, `rate_limited`, `rate_limit_resets_in_seconds`, `available_models`, `usage_stats`, `provider`, `raw_auth`, `raw_error`.

### parse_rate_limit_error

```python
from agentpipe import parse_rate_limit_error, AgentProcessError

try:
    result = await agent.generate("hello")
except AgentProcessError as e:
    info = parse_rate_limit_error("gemini", e)
    if info["rate_limited"]:
        print(f"Rate limited! Resets in {info['resets_in_seconds']}s")
```

Returns a dict with `provider`, `rate_limited` (bool), and `resets_in_seconds` (int or None). Recognizes rate-limit patterns for Gemini, OpenCode, and Claude.

---

## Session Management

```python
agent = Agent("gemini")

# List sessions (Gemini and OpenCode only)
sessions = await agent.list_sessions()
for s in sessions:
    print(s.session_id, s.title, s.created_at, s.provider)

# List models (OpenCode only)
agent = Agent("opencode")
models = await agent.list_models()
for m in models:
    print(m.id, m.name, m.provider)

# Usage stats (OpenCode only)
stats = await agent.stats(days=7, cwd=".")
print(stats)  # {"raw": "..."}
```

---

## Provider Internals

### The Provider Protocol

All providers implement the `Provider` protocol defined in `providers/_base.py`:

```python
from agentpipe import Provider

class Provider(Protocol):
    @property
    def binary_name(self) -> str: ...       # CLI binary name

    @property
    def model(self) -> str | None: ...      # Default model name

    def build_command(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        model: str | None = None,
    ) -> list[str]: ...                     # CLI argv

    def parse_event_line(self, line: str) -> list[AgentEvent]: ...
    def extract_session_id(self, raw_lines: list[str]) -> str | None: ...
    def extract_text(self, raw_lines: list[str]) -> str: ...
    def build_env(self) -> dict[str, str]: ...
```

### Provider Classes

| Class | Binary | Stream Format | Resume | Env Extras | Special |
|---|---|---|---|---|---|
| `ClaudeProvider` | `claude` | `--output-format stream-json` | `--resume <id>` | `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1` | MCP config, approval modes, budget |
| `ClaudeSonnetProvider` | `claude` | same | same | same | model="sonnet" |
| `ClaudeHaikuProvider` | `claude` | same | same | same | model="haiku" |
| `ClaudeOpusProvider` | `claude` | same | same | same | model="opus" |
| `GeminiProvider` | `gemini` | `-o stream-json` | `--resume <id>` | `GEMINI_CLI_TRUST_WORKSPACE=true` | |
| `GeminiFlashProvider` | `gemini` | same | same | same | model="gemini-2.5-flash" |
| `GeminiProProvider` | `gemini` | same | same | same | model="gemini-2.5-pro" |
| `OpencodeProvider` | `opencode` | `--format=json` | `--session <id>` | plain os.environ | backward-compat alias for Zen |
| `OpencodeFreeProvider` | `opencode` | same | same | same | model="opencode/big-pickle", plan="free" |
| `OpencodeZenProvider` | `opencode` | same | same | same | model="opencode/gemini-3-flash", plan="zen" |
| `OpencodeGoProvider` | `opencode` | same | same | same | model="opencode-go/deepseek-v4-flash", plan="go" |

All OpenCode sub-providers share the same CLI binary (`opencode`) and event parsing. The model prefix (`opencode/` vs `opencode-go/`) determines the API endpoint.

### Command Building

Subprocess command construction per provider:

**Claude:**
```
claude -p --dangerously-skip-permissions --output-format stream-json --verbose [--resume <id>] <prompt> --model <model> [--mcp-config <json>] [--max-budget-usd <n>]
```

**Gemini:**
```
gemini -y --model <model> -o stream-json -p <prompt> [--resume <id>]
```

**OpenCode (all variants):**
```
opencode run [--session <id>] <prompt> --model <model> --format=json
```

### Event Parsing

Each provider has its own JSON stream format:

- **Claude:** Emits `system`, `assistant`, `user`, and `result` events. Multi-event lines (`assistant` with multiple content blocks) are expanded. Usage events carry `total_cost_usd`.
- **Gemini:** Emits init, message, tool_use, and tool_result events. Raw JSON lines with `type` field.
- **OpenCode:** Emits `text`, `tool_use`, `step_start`, and `step_finish` events. Cost and token data come from `step_finish`.

Provider-specific parsing lives in the provider classes (`parse_event_line`, `extract_session_id`, `extract_text`). The `AsyncSubprocessExecutor` handles the actual subprocess I/O.

---

## Advanced Usage

### Custom Executors

`Agent` accepts an `executor` parameter for dependency injection:

```python
from agentpipe import Agent, AsyncSubprocessExecutor

executor = AsyncSubprocessExecutor()
agent = Agent("claude", executor=executor)
```

This is useful for testing (mock the executor) or for sharing a single executor instance across agents.

### Error Handling

```python
from agentpipe import Agent, AgentProcessError

agent = Agent("gemini")

try:
    result = await agent.generate("hello")
except AgentProcessError as e:
    print(f"Process exited with code {e.returncode}")
    print(f"stderr: {e.stderr}")
    print(f"argv: {e.argv}")
```

`AgentProcessError` extends `RuntimeError` with `returncode`, `stderr`, and `argv` attributes.

The cascade system catches `AgentProcessError`, `asyncio.TimeoutError`, and generic exceptions, classifying each as `ErrorType.RATE_LIMIT`, `ErrorType.PROCESS_ERROR`, `ErrorType.TIMEOUT`, or `ErrorType.UNKNOWN`.

### Integrating with Other Frameworks

agentpipe has zero dependencies and uses only `asyncio.create_subprocess_exec`. It works alongside any async framework (FastAPI, aiohttp, etc.) and doesn't interfere with event loops.

```python
# FastAPI example
from fastapi import FastAPI
from agentpipe import cascade_free_only

app = FastAPI()

@app.get("/ask")
async def ask(q: str):
    result = await cascade_free_only(q, per_attempt_timeout=30)
    return {"answer": result.text, "model": result.successful_model}
```

---

## Feature Matrix

| Feature | Claude | Gemini | OpenCode |
|---------|--------|--------|----------|
| MCP servers | Runtime (`--mcp-config`) | Config only | Config only |
| Approval modes | `--permission-mode` / `--dangerously-skip-permissions` | `--yolo` | Config only |
| Budget cap | `--max-budget-usd` | — | — |
| Session resume | `--resume <id>` | `--resume <id>` | `--session <id>` |
| Stream format | `stream-json` | `stream-json` | `--format=json` |
| List sessions | — | `--list-sessions` | `opencode session list` |
| List models | — | — | `opencode models` |
| Auth status | `claude auth status --json` | CLI check | `opencode providers list` |
| Stats | Per-invocation | Per-invocation | `opencode stats` |
| Plan variants | Sonnet / Haiku / Opus | Flash / Pro | Free / Zen / Go |

---

## API Reference

### Top-Level Imports

```python
from agentpipe import (
    # Core
    Agent, AgentSession, AgentProcessError, AsyncSubprocessExecutor,

    # Types
    AgentEvent, ThinkingEvent, ToolCallEvent, ToolResultEvent, UsageEvent,
    GenerationResult, SessionInfo, SessionUsage, CommandSpec,
    ApprovalMode, AuthStatus, ModelInfo, SessionEntry,
    McpServerConfig, HttpMcpServer, StdioMcpServer,
    Provider, QuotaStatus,

    # Constants
    DEFAULT_CWD, DEFAULT_MODELS,

    # Pipeline
    fan_out, delegate, retry_until, map_concurrent,

    # Cascade
    cascade, cascade_coding, cascade_fast_free, cascade_free_only,
    CASCADE_PROFILES, MODEL_TIER_MAP, ModelTier, ErrorType,
    CascadeAttempt, CascadeResult, tier_summary,

    # Provider classes
    ClaudeProvider, ClaudeSonnetProvider, ClaudeHaikuProvider, ClaudeOpusProvider,
    GeminiProvider, GeminiFlashProvider, GeminiProProvider,
    OpencodeProvider, OpencodeFreeProvider, OpencodeZenProvider, OpencodeGoProvider,

    # Quota
    check_quota, parse_rate_limit_error,
)
```

### Key Defaults

| Constant | Value |
|----------|-------|
| `DEFAULT_CWD` | `"/tmp"` |
| `DEFAULT_MODELS["claude"]` | `"sonnet"` |
| `DEFAULT_MODELS["gemini"]` | `"gemini-2.5-flash"` |
| `DEFAULT_MODELS["opencode"]` | `"opencode/gemini-3-flash"` |
| `DEFAULT_MODELS["opencode-free"]` | `"opencode/big-pickle"` |
| `DEFAULT_MODELS["opencode-zen"]` | `"opencode/gemini-3-flash"` |
| `DEFAULT_MODELS["opencode-go"]` | `"opencode-go/deepseek-v4-flash"` |
| Agent default timeout | `300` seconds |
| Cascade default timeout | `120` seconds per attempt |