# Provider Internals

## The Provider Protocol

All providers implement the `Provider` protocol defined in `providers/_base.py`:

```python
from agentpipe import Provider

class Provider(Protocol):
    @property
    def binary_name(self) -> str: ...
    # CLI binary name (e.g. "claude", "gemini", "opencode")

    @property
    def model(self) -> str | None: ...
    # Default model name (may be None)

    def build_command(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        model: str | None = None,
    ) -> list[str]: ...
    # Build the CLI argv list

    def parse_event_line(self, line: str) -> list[AgentEvent]: ...
    # Parse a single line from stdout into AgentEvent(s)

    def extract_session_id(self, raw_lines: list[str]) -> str | None: ...
    # Extract session ID from raw output lines

    def extract_text(self, raw_lines: list[str]) -> str: ...
    # Extract the text output from raw output lines

    def build_env(self) -> dict[str, str]: ...
    # Build environment variables for the subprocess
```

## Provider Classes

| Class | Binary | Default Model | Plan | Env Extras |
|---|---|---|---|---|
| `ClaudeProvider` | `claude` | `None` (uses DEFAULT_MODELS) | — | `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1` |
| `ClaudeSonnetProvider` | `claude` | `sonnet` | — | same |
| `ClaudeHaikuProvider` | `claude` | `haiku` | — | same |
| `ClaudeOpusProvider` | `claude` | `opus` | — | same |
| `GeminiProvider` | `gemini` | `None` | — | `GEMINI_CLI_TRUST_WORKSPACE=true` |
| `GeminiFlashProvider` | `gemini` | `gemini-2.5-flash` | — | same |
| `GeminiProProvider` | `gemini` | `gemini-2.5-pro` | — | same |
| `OpencodeProvider` | `opencode` | `opencode/gemini-3-flash` | `zen` | plain `os.environ` |
| `OpencodeFreeProvider` | `opencode` | `opencode/big-pickle` | `free` | plain `os.environ` |
| `OpencodeZenProvider` | `opencode` | `opencode/gemini-3-flash` | `zen` | plain `os.environ` |
| `OpencodeGoProvider` | `opencode` | `opencode-go/deepseek-v4-flash` | `go` | plain `os.environ` |

`OpencodeProvider` is the base class. `OpencodeFreeProvider`, `OpencodeZenProvider`, and `OpencodeGoProvider` inherit from it and set different default models and `plan` properties. `OpencodeProvider()` is a backward-compat alias that behaves identically to `OpencodeZenProvider()`.

## Command Building

Each provider constructs CLI commands differently:

### Claude

```
claude -p --dangerously-skip-permissions --output-format stream-json --verbose [--resume <id>] <prompt> --model <model> [--mcp-config <json>] [--max-budget-usd <n>]
```

The `--dangerously-skip-permissions` flag is used by default (or with `YOLO`/`BYPASS` approval modes). Other modes get `--permission-mode <mode>` instead.

MCP servers are serialized to JSON and passed via `--mcp-config`. Budget caps use `--max-budget-usd`.

### Gemini

```
gemini -y --model <model> -o stream-json -p <prompt> [--resume <id>]
```

The `-y` flag auto-accepts prompts. `-p <prompt>` sends the prompt as a flag (not stdin, since Gemini doesn't support stdin). `GEMINI_CLI_TRUST_WORKSPACE=true` is injected to allow running in `/tmp`.

### OpenCode (all variants)

```
opencode run [--session <id>] <prompt> --model <model> --format=json
```

All three sub-providers (Free, Zen, Go) use the same binary and command format. The model prefix (`opencode/` vs `opencode-go/`) determines the API endpoint.

## Event Parsing

Each provider emits different JSON stream formats:

### Claude

Emits `system`, `assistant`, `user`, and `result` events in `stream-json` format:
- `system` → extracts `session_id`
- `assistant` → may contain multiple content blocks (text, tool_use) in a single line → expanded into individual events
- `user` → tool_result blocks
- `result` → final text, usage (`input_tokens`, `output_tokens`, `cache_*`), and `total_cost_usd`

### Gemini

Emits init, message, tool_use, and tool_result events:
- Init event contains session ID
- `assistant` role messages → `ThinkingEvent`
- Tool use events → `ToolCallEvent` with `tool_id`
- Tool result events → `ToolResultEvent` with duration tracking

### OpenCode

Emits `text`, `tool_use`, `step_start`, and `step_finish` events:
- `text` type → `ThinkingEvent`
- `tool_use` with `state.input` → `ToolCallEvent`; with `state.output` → `ToolResultEvent`
- `step_finish` → `UsageEvent` with `cost` and `tokens` (including `cache.read`/`cache.write`)

Provider-specific parsing lives in the provider classes (`parse_event_line`, `extract_session_id`, `extract_text`).

## Subprocess Execution

The `AsyncSubprocessExecutor` class handles all subprocess I/O:

```python
from agentpipe import AsyncSubprocessExecutor, CommandSpec

executor = AsyncSubprocessExecutor()

# Stream stdout/stderr lines as they arrive
async for stream, line in executor.run_streaming(spec):
    if stream == "stdout":
        events = provider.parse_event_line(line)
        ...

# Or get the full result at once
stdout, stderr = await executor.run(spec)

# Check binary availability
path = await executor.check_binary("claude")
```

`CommandSpec` fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `argv` | `list[str]` | *(required)* | Command and arguments |
| `stdin` | `str` | *(required)* | Input to send to stdin |
| `cwd` | `str | None` | `None` | Working directory |
| `env` | `dict[str, str] | None` | `None` | Environment variables |
| `timeout` | `float` | `300.0` | Seconds before kill |