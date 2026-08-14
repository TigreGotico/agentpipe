# Core API

## Agent Dataclass

```python
from agentpipe import Agent, ApprovalMode, EffortLevel, HttpMcpServer

agent = Agent(
    provider="claude-sonnet",      # str : provider name or alias
    model=None,                    # str | None : override (filled from DEFAULT_MODELS if None)
    cwd="/tmp",                    # str : working directory for subprocesses
    timeout=300,                   # int : seconds before killing the subprocess
    mcp_servers=[],               # list[McpServerConfig] : MCP servers (Claude, OpenCode)
    approval_mode=None,            # ApprovalMode | None : approval mode (all providers)
    max_budget_usd=None,           # float | None : budget cap (Claude only)
    # Tool allow/deny + system prompt
    system_prompt=None,            # str | None : system prompt (Claude)
    append_system_prompt=None,     # str | None : append to system prompt (Claude)
    allowed_tools=None,            # list[str] | None : allowed tools (Claude, Gemini)
    disallowed_tools=None,         # list[str] | None : disallowed tools (Claude)
    # Effort + structured output + fallback
    effort=None,                   # EffortLevel | None : effort level (Claude, OpenCode variant)
    fallback_model=None,           # str | None : fallback model (Claude)
    json_schema=None,              # dict | None : JSON schema for structured output (Claude)
    # Session lifecycle
    session_name=None,             # str | None : session name (Claude --name, OpenCode --title)
    continue_last=False,           # bool : continue last session (Claude, OpenCode)
    fork_session=False,            # bool : fork session (Claude --fork-session, OpenCode --fork)
    # Files
    files=None,                    # list[str] | None : file attachments (Claude, OpenCode)
    # Agent selection
    agent_name=None,               # str | None : agent name (Claude, OpenCode)
    # Sandbox and output control
    sandbox=False,                 # bool : sandbox mode (all providers)
    raw_output=False,              # bool : raw output without verbose (Claude, Gemini)
    include_dirs=None,             # list[str] | None : additional directories (all providers)
)
```

`Agent` is a `@dataclass` with a `__post_init__` that:
1. Resolves `model` from `DEFAULT_MODELS` if `None`
2. Validates `provider` against `PROVIDER_MAP`
3. Builds `_provider_instance` with all relevant fields forwarded to the provider

Invalid provider names raise `ValueError` with the list of available providers.

## Generation Methods

All generation methods are `async`. agentpipe spawns one subprocess per call : no persistent daemons.

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
print(result.text)         # str : extracted text
print(result.events)       # tuple[AgentEvent, ...] : all parsed events
print(result.session_id)   # str | None : for resuming
print(result.usage)        # UsageEvent | None
print(result.returncode)   # int : process exit code
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

`AgentSession` is an async context manager that auto-resumes. The first `generate()` call has no resume flag. Subsequent calls include `--resume <session_id>`.

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

# Not typically constructed directly : use agent.session()
session = agent.session(cwd=".", timeout=120)
async with session as sess:
    # sess.session_id : str | None (set after first generate)
    # sess.usage : SessionUsage (accumulates across turns)
    text = await sess.generate("prompt")
```

## Other Agent Methods

```python
# Check if the CLI binary is on PATH
path: str = await agent.check_available()

# Get auth status
status: AuthStatus = await agent.auth_status()
# status.authenticated, status.email, status.subscription_type, ...

# Login / logout (Claude, OpenCode)
status: AuthStatus = await agent.auth_login(method="api_key")
status: AuthStatus = await agent.auth_logout()

# Session management (OpenCode, Gemini)
sessions: list[SessionEntry] = await agent.list_sessions()
deleted: bool = await agent.delete_session("sess-id")
export: SessionExport = await agent.export_session("sess-id")
new_id: str | None = await agent.import_session(json_data)

# List models (OpenCode only)
models: list[ModelInfo] = await agent.list_models()

# Stats (OpenCode only)
stats: dict = await agent.stats(days=7, cwd=".")

# MCP management (Claude, OpenCode)
added: bool = await agent.mcp_add("github", command="npx", args=["-y", "@mcp/server-github"])
added: bool = await agent.mcp_add("docs", url="http://localhost:9000/sse")
removed: bool = await agent.mcp_remove("github")
servers: list[McpServerInfo] = await agent.mcp_list()

# Extensions (Gemini only)
extensions: list[ExtensionInfo] = await agent.list_extensions()

# Doctor (Claude only)
result: dict = await agent.doctor()
```

## Effort Levels

Claude supports effort levels that control how much reasoning the model applies:

```python
from agentpipe import Agent, EffortLevel

agent = Agent("claude", effort=EffortLevel.HIGH)
# LOW, MEDIUM, HIGH, VERY_HIGH ("xhigh"), MAX
```

## Tool Allow/Deny

Restrict which tools Claude can use:

```python
agent = Agent("claude", allowed_tools=["Read", "Write", "Grep"])
agent = Agent("claude", disallowed_tools=["Bash", "rm"])
```

## Structured Output

Request JSON output matching a schema (Claude):

```python
schema = {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}}
agent = Agent("claude", json_schema=schema)
```

## Sandbox Mode

Run the agent in a sandbox (Claude, Gemini, OpenCode):

```python
agent = Agent("claude", sandbox=True)
```

---
[← Providers and Models](providers.md) · [Home](index.md) · [Pipeline Functions →](pipelines.md)