# API Reference

## Top-Level Imports

```python
from agentpipe import (
    # Core
    Agent, AgentSession, AgentProcessError, AsyncSubprocessExecutor,

    # Types
    AgentEvent, ThinkingEvent, ToolCallEvent, ToolResultEvent, UsageEvent,
    GenerationResult, SessionInfo, SessionUsage, CommandSpec,
    ApprovalMode, EffortLevel, AuthStatus, ModelInfo, SessionEntry, SessionExport,
    McpServerConfig, HttpMcpServer, StdioMcpServer, McpServerInfo, ExtensionInfo,
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
    AiderProvider,
    ClaudeProvider, ClaudeSonnetProvider, ClaudeHaikuProvider, ClaudeOpusProvider,
    GeminiProvider, GeminiFlashProvider, GeminiProProvider,
    KiloProvider,
    OpencodeProvider, OpencodeFreeProvider, OpencodeZenProvider, OpencodeGoProvider,
    QoderProvider, VibeProvider,

    # Quota
    check_quota, parse_rate_limit_error,
)
```

## Agent

```python
@dataclass
class Agent:
    provider: str                              # "claude", "claude-sonnet", "gemini-flash", "opencode-free", etc.
    model: str | None = None                  # Override (filled from DEFAULT_MODELS if None)
    cwd: str = "/tmp"                          # Working directory for subprocesses
    timeout: int = 300                         # Seconds before killing the subprocess
    mcp_servers: list[McpServerConfig] = []    # Claude MCP servers
    approval_mode: ApprovalMode | None = None  # Claude permission mode
    max_budget_usd: float | None = None        # Claude budget cap
    # Tool allow/deny + system prompt
    system_prompt: str | None = None           # Claude system prompt override
    append_system_prompt: str | None = None    # Claude append to system prompt
    allowed_tools: list[str] | None = None     # Claude allowed tools
    disallowed_tools: list[str] | None = None  # Claude disallowed tools
    # Effort + structured output + fallback
    effort: EffortLevel | None = None          # Claude effort level
    fallback_model: str | None = None          # Claude fallback model
    json_schema: dict | None = None            # Claude JSON schema
    # Session lifecycle
    session_name: str | None = None            # Session name
    continue_last: bool = False                # Continue last session
    fork_session: bool = False                 # Fork session
    # Files
    files: list[str] | None = None             # File attachments
    # Agent selection
    agent_name: str | None = None              # Claude agent name
    # Sandbox and output control
    sandbox: bool = False                       # Sandbox mode
    raw_output: bool = False                    # Raw output (no verbose)
    include_dirs: list[str] | None = None      # Additional directories
    executor: AsyncSubprocessExecutor = ...     # Dependency injection
```

### Methods

| Method | Signature | Return | Providers |
|---|---|---|---|
| `generate` | `(self, prompt, *, cwd=None, timeout=None)` | `str` | All |
| `generate_stream` | `(self, prompt, *, cwd=None, timeout=None)` | `AsyncIterator[AgentEvent]` | All |
| `generate_full` | `(self, prompt, *, cwd=None, timeout=None)` | `GenerationResult` | All |
| `session` | `(self, *, cwd=None, timeout=None)` | `AgentSession` | All |

| Method | Signature | Return | Providers |
|---|---|---|---|
| `check_available` | `(self)` | `str` | All |
| `auth_status` | `(self)` | `AuthStatus` | All |
| `auth_login` | `(self, *, method=None)` | `AuthStatus` | Claude, OpenCode |
| `auth_logout` | `(self)` | `AuthStatus` | Claude, OpenCode |

| Method | Signature | Return | Providers |
|---|---|---|---|
| `list_sessions` | `(self, *, cwd=None)` | `list[SessionEntry]` | Gemini, OpenCode |
| `delete_session` | `(self, session_id, *, cwd=None)` | `bool` | OpenCode |
| `export_session` | `(self, session_id, *, cwd=None)` | `SessionExport` | OpenCode |
| `import_session` | `(self, data, *, cwd=None)` | `str \| None` | OpenCode |

| Method | Signature | Return | Providers |
|---|---|---|---|
| `list_models` | `(self)` | `list[ModelInfo]` | OpenCode |
| `stats` | `(self, *, days=None, cwd=None)` | `dict` | OpenCode |
| `mcp_add` | `(self, name, *, url=None, command=None, args=None, env=None, headers=None, scope=None)` | `bool` | Claude, OpenCode |
| `mcp_remove` | `(self, name, *, scope=None)` | `bool` | Claude, OpenCode |

| Method | Signature | Return | Providers |
|---|---|---|---|
| `mcp_list` | `(self)` | `list[McpServerInfo]` | Claude, OpenCode |
| `list_extensions` | `(self)` | `list[ExtensionInfo]` | Gemini |
| `doctor` | `(self)` | `dict` | Claude |

## Constants

| Constant | Value |
|---|---|
| `DEFAULT_CWD` | `"/tmp"` |
| `DEFAULT_MODELS["aider"]` | `"openrouter/google/gemma-4-26b-a4b-it:free"` |
| `DEFAULT_MODELS["claude"]` | `"sonnet"` |
| `DEFAULT_MODELS["claude-sonnet"]` | `"sonnet"` |

| Constant | Value |
|---|---|
| `DEFAULT_MODELS["claude-haiku"]` | `"haiku"` |
| `DEFAULT_MODELS["claude-opus"]` | `"opus"` |
| `DEFAULT_MODELS["gemini"]` | `"gemini-2.5-flash"` |
| `DEFAULT_MODELS["gemini-flash"]` | `"gemini-2.5-flash"` |

| Constant | Value |
|---|---|
| `DEFAULT_MODELS["gemini-pro"]` | `"gemini-2.5-pro"` |
| `DEFAULT_MODELS["kilo"]` | `"kilo/kilo-auto/free"` |
| `DEFAULT_MODELS["opencode"]` | `"opencode/gemini-3-flash"` |
| `DEFAULT_MODELS["opencode-free"]` | `"opencode/big-pickle"` |

| Constant | Value |
|---|---|
| `DEFAULT_MODELS["opencode-zen"]` | `"opencode/gemini-3-flash"` |
| `DEFAULT_MODELS["opencode-go"]` | `"opencode-go/deepseek-v4-flash"` |
| `DEFAULT_MODELS["qoder"]` | `"mistral-large-latest"` |
| `DEFAULT_MODELS["vibe"]` | `"mistral-large-latest"` |

## Enums

```python
class ApprovalMode(str, Enum):
    DEFAULT = "default"
    AUTO_EDIT = "auto_edit"
    YOLO = "yolo"
    PLAN = "plan"
    BYPASS = "bypass"

class EffortLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "xhigh"
    MAX = "max"

class ModelTier(int, Enum):
    FREE = 0
    CHEAP = 1
    MID = 2
    PREMIUM = 3

class ErrorType(str, Enum):
    RATE_LIMIT = "rate_limit"
    PROCESS_ERROR = "process_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"
```

## Dataclasses

### ThinkingEvent (frozen)
`text: str`

### ToolCallEvent (frozen)
`tool: str`, `args: dict | str | None = None`, `tool_id: str | None = None`

### ToolResultEvent (frozen)
`tool: str`, `output: str = ""`, `exit_code: int | None = None`, `duration_ms: float | None = None`

### UsageEvent (frozen)
`input_tokens: int = 0`, `output_tokens: int = 0`, `cost_usd: float | None = None`, `cache_read_tokens: int = 0`, `cache_write_tokens: int = 0`

### GenerationResult (frozen)
`text: str`, `events: tuple[AgentEvent, ...] = ()`, `session_id: str | None = None`, `usage: UsageEvent | None = None`, `returncode: int = 0`

### SessionInfo (mutable)
`session_id: str | None = None`

### SessionUsage (mutable)
`total_input_tokens: int = 0`, `total_output_tokens: int = 0`, `total_cost_usd: float = 0.0`, `total_cache_read_tokens: int = 0`, `total_cache_write_tokens: int = 0`, `turn_count: int = 0`. Method: `add(usage: UsageEvent)`.

### CommandSpec (frozen)
`argv: list[str]`, `stdin: str`, `cwd: str | None = None`, `env: dict[str, str] | None = None`, `timeout: float = 300.0`

### HttpMcpServer (frozen)
`name: str`, `url: str`, `headers: dict[str, str] = {}`

### StdioMcpServer (frozen)
`name: str`, `command: str`, `args: list[str] = []`, `env: dict[str, str] = {}`

### AuthStatus (frozen)
`authenticated: bool`, `provider: str`, `email: str | None = None`, `method: str | None = None`, `subscription_type: str | None = None`, `raw: dict | None = None`

### SessionEntry (frozen)
`session_id: str`, `title: str | None = None`, `created_at: str | None = None`, `provider: str | None = None`

### ModelInfo (frozen)
`id: str`, `name: str | None = None`, `provider: str | None = None`, `context_window: int | None = None`, `cost_per_million_input: float | None = None`, `cost_per_million_output: float | None = None`

### McpServerInfo (frozen)
`name: str`, `type: str | None = None`, `url: str | None = None`, `command: str | None = None`, `args: list[str] | None = None`, `env: dict[str, str] | None = None`, `headers: dict[str, str] | None = None`, `scope: str | None = None`, `enabled: bool | None = None`

### ExtensionInfo (frozen)
`name: str`, `version: str | None = None`, `description: str | None = None`, `enabled: bool | None = None`

### SessionExport (frozen)
`session_id: str`, `data: str`, `format: str = "json"`

### QuotaStatus (mutable)
`authenticated: bool = False`, `subscription_type: str | None = None`, `email: str | None = None`, `plan_limits: dict = {}`, `rate_limited: bool = False`, `rate_limit_resets_in_seconds: int | None = None`, `available_models: list[str] = []`, `usage_stats: dict = {}`, `provider: str | None = None`, `raw_auth: dict | None = None`, `raw_error: str | None = None`

### CascadeAttempt (mutable)
`model: str`, `provider: str`, `success: bool`, `error_type: ErrorType | None = None`, `error_message: str | None = None`, `rate_limit_resets_in: int | None = None`, `cost_usd: float | None = None`, `input_tokens: int = 0`, `output_tokens: int = 0`, `duration_seconds: float = 0.0`, `result_text: str | None = None`

### CascadeResult (mutable)
`text: str`, `attempts: list[CascadeAttempt] = []`, `total_cost_usd: float = 0.0`, `total_duration_seconds: float = 0.0`, `successful_model: str | None = None`, `successful_provider: str | None = None`. Properties: `attempt_count`, `failed_attempts`, `rate_limited_models`.

## Type Aliases

```python
AgentEvent = ThinkingEvent | ToolCallEvent | ToolResultEvent | UsageEvent
McpServerConfig = HttpMcpServer | StdioMcpServer
```

## Exceptions

### AgentProcessError(RuntimeError)
`returncode: int`, `stderr: str`, `argv: list[str]`. Message: `"Agent process exited with code {returncode}: {last_line_of_stderr}"`.

## Cascade Functions

| Function | Signature | Return |
|---|---|---|
| `cascade` | `(prompt, *, models=None, profile="default", max_tier=None, max_attempts=10, max_cost_usd=None, max_total_seconds=None, per_attempt_timeout=120, retry_delay_seconds=2.0, rate_limit_backoff_seconds=10, cwd="/tmp", on_attempt=None)` | `CascadeResult` |
| `cascade_coding` | `(prompt, *, max_tier=CHEAP, **kwargs)` | `CascadeResult` |
| `cascade_fast_free` | `(prompt, **kwargs)` | `CascadeResult` |
| `cascade_free_only` | `(prompt, **kwargs)` | `CascadeResult` |

| Function | Signature | Return |
|---|---|---|
| `tier_summary` | `()` | `dict[ModelTier, list[dict]]` |

## Pipeline Functions

| Function | Signature | Return |
|---|---|---|
| `fan_out` | `(agent, prompts, *, max_concurrency=5, cwd=None, timeout=300)` | `list[str]` |
| `delegate` | `(drafter, reviewer, draft_prompt, review_prompt=None, *, cwd=None, timeout=300)` | `str` |
| `retry_until` | `(agent, prompt, *, validator, max_attempts=3, refine_prompt=None, cwd=None, timeout=300)` | `str` |
| `map_concurrent` | `(agents, prompt, *, cwd=None, timeout=300)` | `list[str]` |

## Quota Functions

| Function | Signature | Return |
|---|---|---|
| `check_quota` | `(provider=None, *, model=None, executor=None)` | `QuotaStatus` |
| `parse_rate_limit_error` | `(provider, error)` | `dict` with `provider`, `rate_limited`, `resets_in_seconds` |

---
[← Feature Matrix](feature-matrix.md) · [Home](index.md)