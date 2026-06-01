# Core API

## Agent Dataclass

```python
from agentpipe import Agent, ApprovalMode, HttpMcpServer

agent = Agent(
    provider="claude-sonnet",      # str — provider name or alias
    model=None,                    # str | None — override (filled from DEFAULT_MODELS if None)
    cwd="/tmp",                    # str — working directory for subprocesses
    timeout=300,                   # int — seconds before killing the subprocess
    mcp_servers=[],               # list[McpServerConfig] — Claude MCP servers
    approval_mode=None,            # ApprovalMode | None — Claude permission mode
    max_budget_usd=None,          # float | None — Claude budget cap
)
```

`Agent` is a `@dataclass` with a `__post_init__` that:
1. Resolves `model` from `DEFAULT_MODELS` if `None`
2. Validates `provider` against `PROVIDER_MAP`
3. Builds `_provider_instance` with model, mcp_servers, approval_mode, max_budget_usd

Invalid provider names raise `ValueError` with the list of available providers.

## Generation Methods

All generation methods are `async`. agentpipe spawns one subprocess per call — no persistent daemons.

### generate()

Returns just the text:

```python
text: str = await agent.generate("Explain this function")
```

### generate_full()

Returns a structured result with events, usage, and session ID:

```python
from agentpipe import GenerationResult

result: GenerationResult = await agent.generate_full("Refactor this module")
print(result.text)         # str — extracted text
print(result.events)       # tuple[AgentEvent, ...] — all parsed events
print(result.session_id)   # str | None — for resuming
print(result.usage)        # UsageEvent | None
print(result.returncode)   # int — process exit code
```

### generate_stream()

Yields streaming events as they arrive:

```python
async for event in agent.generate_stream("Explain architecture"):
    match event:
        case ThinkingEvent(text=t):     print(t, end="")
        case ToolCallEvent(tool=name):  print(f"[tool: {name}]")
        case ToolResultEvent(tool=name, output=out): print(f"[{name}: {out[:50]}]")
        case UsageEvent(input_tokens=n): print(f"Tokens: {n}")
```

All three methods accept `cwd` and `timeout` overrides:

```python
result = await agent.generate("prompt", cwd="/home/user/project", timeout=120)
```

## Multi-Turn Sessions

`AgentSession` is an async context manager that auto-resumes. The first `generate()` call has no resume flag; subsequent calls include `--resume <session_id>`.

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

### SessionUsage

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `total_input_tokens` | `int` | `0` | Cumulative input tokens |
| `total_output_tokens` | `int` | `0` | Cumulative output tokens |
| `total_cost_usd` | `float` | `0.0` | Cumulative cost |
| `total_cache_read_tokens` | `int` | `0` | Cumulative cache reads |
| `total_cache_write_tokens` | `int` | `0` | Cumulative cache writes |
| `turn_count` | `int` | `0` | Number of `generate()` calls |

The `add(usage: UsageEvent)` method accumulates a single turn's usage into the totals.

## Event Types

All events are frozen dataclasses. `AgentEvent` is a union of the four types below.

### ThinkingEvent

```python
ThinkingEvent(text: str)
```

Emitted for model text output (including Claude's assistant text, Gemini message content, and OpenCode text events).

### ToolCallEvent

```python
ToolCallEvent(tool: str, args: dict | str | None = None, tool_id: str | None = None)
```

Emitted when the model invokes a tool. `tool_id` is available for Claude and Gemini.

### ToolResultEvent

```python
ToolResultEvent(tool: str, output: str = "", exit_code: int | None = None, duration_ms: float | None = None)
```

Emitted when a tool execution completes. `duration_ms` is available for Claude and Gemini.

### UsageEvent

```python
UsageEvent(
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float | None = None,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
)
```

Emitted at the end of each step/tool call with token counts and cost. `cost_usd` is `None` for providers that don't report it.

## GenerationResult

```python
GenerationResult(
    text: str,                           # extracted text
    events: tuple[AgentEvent, ...] = (), # all parsed events
    session_id: str | None = None,       # for resuming
    usage: UsageEvent | None = None,      # token/cost summary
    returncode: int = 0,                 # process exit code
)
```

## AgentSession

```python
from agentpipe import AgentSession

# Not typically constructed directly — use agent.session()
session = agent.session(cwd=".", timeout=120)
async with session as sess:
    # sess.session_id — str | None (set after first generate)
    # sess.usage — SessionUsage (accumulates across turns)
    text = await sess.generate("prompt")
```

## Other Agent Methods

```python
# Check if the CLI binary is on PATH
path: str = await agent.check_available()

# Get auth status
status: AuthStatus = await agent.auth_status()
# status.authenticated, status.email, status.subscription_type, ...

# List sessions (Gemini and OpenCode only)
sessions: list[SessionEntry] = await agent.list_sessions()

# List models (OpenCode only)
models: list[ModelInfo] = await agent.list_models()

# Stats (OpenCode only)
stats: dict = await agent.stats(days=7, cwd=".")
```