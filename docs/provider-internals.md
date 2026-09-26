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

    def detect_error(self, raw_lines: list[str]) -> str | None: ...
    # Report a failure the CLI printed while still exiting 0, or None

    def build_env(self) -> dict[str, str]: ...
    # Build environment variables for the subprocess
```

Most CLIs report failures through their exit code and their `detect_error`
returns `None` in one line. Implement it when the CLI can print an error and
still exit 0 — aider does this, and without it the error text was returned as
the assistant's answer. The session calls it after the run and raises
`ProviderOutputError` when it returns a string, so a provider that reports a
recoverable hiccup here turns a working answer into a failed request.

## Provider Classes

| Class | Binary | Default Model | Plan | Env Extras |
|---|---|---|---|---|
| `ClaudeProvider` | `claude` | `None` (uses DEFAULT_MODELS) | n/a | `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1` |
| `ClaudeSonnetProvider` | `claude` | `sonnet` | n/a | same |
| `ClaudeHaikuProvider` | `claude` | `haiku` | n/a | same |
| `ClaudeOpusProvider` | `claude` | `opus` | n/a | same |
| `GeminiProvider` | `gemini` | `None` | n/a | `GEMINI_CLI_TRUST_WORKSPACE=true` |
| `GeminiFlashProvider` | `gemini` | `gemini-2.5-flash` | n/a | same |
| `GeminiProProvider` | `gemini` | `gemini-2.5-pro` | n/a | same |
| `OpencodeProvider` | `opencode` | `opencode/gemini-3-flash` | `zen` | plain `os.environ` |
| `OpencodeFreeProvider` | `opencode` | `opencode/big-pickle` | `free` | plain `os.environ` |
| `OpencodeZenProvider` | `opencode` | `opencode/gemini-3-flash` | `zen` | plain `os.environ` |
| `OpencodeGoProvider` | `opencode` | `opencode-go/deepseek-v4-flash` | `go` | plain `os.environ` |
| `QoderProvider` | `qodercli` | `None` (uses QoderCLI default) | n/a | plain `os.environ` |
| `VibeProvider` | `vibe` | `mistral-large-latest` | n/a | `MISTRAL_API_KEY` |

`OpencodeProvider` is the base class. `OpencodeFreeProvider`, `OpencodeZenProvider`, and `OpencodeGoProvider` inherit from it and set different default models and `plan` properties. `OpencodeProvider()` is a backward-compat alias that behaves identically to `OpencodeZenProvider()`.

`QoderProvider` mirrors the Claude Code CLI interface since QoderCLI is architecturally similar (same `-p`, `--permission-mode`, `--output-format stream-json`, `--dangerously-skip-permissions` flags). `VibeProvider` uses Mistral's `vibe` binary with `--prompt` and `--output streaming` flags.

## Command Building

Each provider constructs CLI commands differently:

### Claude

```
claude -p [--dangerously-skip-permissions | --permission-mode <mode>]
    [--system-prompt <prompt>] [--append-system-prompt <prompt>]
    [--allowedTools <tool>]... [--disallowedTools <tool>]...
    [--effort <level>] [--fallback-model <model>]
    [--output-format stream-json] [--verbose]
    [--json-schema <schema>] [--sandbox] [--agent <name>]
    [--name <session>] [--continue] [--fork-session]
    [--add-dir <dir>]... [--file <spec>]...
    [--resume <id>] <prompt> --model <model>
    [--mcp-config <json>] [--strict-mcp-config] [--max-budget-usd <n>]
```

The `--dangerously-skip-permissions` flag is used by default (or with `YOLO`/`BYPASS` approval modes). Other modes get `--permission-mode <mode>` instead. `--verbose` is omitted when `raw_output=True`. `--json-schema` switches output format to `json`.

MCP servers are serialized to JSON and passed via `--mcp-config`. Budget caps use `--max-budget-usd`.

### Gemini

```
gemini [--yolo | --approval-mode <mode>] --model <model>
    [--sandbox] [--include-directories <dir>]...
    [--allowed-tools <tool>]... [--extensions <ext>]...
    [--output-format stream-json | --output-format json --raw-output]
    -p <prompt> [--resume <id>]
```

The `-y` flag is for non-interactive mode. Approval mode maps: YOLO/BYPASS → `--yolo`, others → `--approval-mode <mode>`.

### OpenCode (all variants)

```
opencode run [--session <id>] [--continue] [--fork]
    [--dangerously-skip-permissions] [--sandbox]
    [--agent <name>] [--title <session>]
    --model <model> [--variant <effort>]
    [--dir <dir>]... [--file <file>]...
    <prompt> --format=json
```

All three sub-providers (Free, Zen, Go) use the same binary and command format. The model prefix (`opencode/` vs `opencode-go/`) determines the API endpoint. Effort level maps: low→minimal, medium→low, high→high, xhigh/max→max.

### QoderCLI

```
qodercli -p [--dangerously-skip-permissions | --permission-mode <mode>]
    [--system-prompt <prompt>] [--append-system-prompt <prompt>]
    [--allowed-tools <tool>]... [--disallowed-tools <tool>]...
    [--effort <level>] [--fallback-model <model>]
    [--output-format stream-json] [--verbose]
    [--json-schema <schema>] [--sandbox] [--agent <name>]
    [--name <session>] [--continue] [--fork-session]
    [--add-dir <dir>]... [--file <spec>]...
    [--max-turns <n>]
    [--resume <id>] <prompt> --model <model>
    [--mcp-config <json>] [--strict-mcp-config] [--max-budget-usd <n>]
```

QoderCLI mirrors Claude Code's CLI interface closely (same flags, same streaming format). It includes additional `--max-turns` and `--allowed-mcp-server-names` flags.

### Vibe

```
vibe --prompt <prompt> [--agent <name>]
    [--continue] [--resume <id>]
    [--sandbox] [--add-dir <dir>]...
    [--enabled-tools <tool>]...
    [--max-turns <n>] [--max-price <dollars>] [--max-tokens <n>]
    --output streaming
```

Vibe uses `--prompt` (not stdin), `--continue`/`--resume` for sessions, `--output streaming` for NDJSON, and `--agent` for approval profiles (default, plan, accept-edits, auto-approve). It does not support system prompts, MCP config, or effort levels via CLI flags. Those settings are configured through `~/.vibe/config.toml`.

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

### QoderCLI

Uses the same `stream-json` format as Claude Code:
- `system` → extracts `session_id`
- `assistant` → may contain multiple content blocks (text, tool_use) in a single line → expanded into individual events
- `user` → tool_result blocks
- `result` → final text, usage (`input_tokens`, `output_tokens`, `cache_*`), and `total_cost_usd`

### Vibe

Emits newline-delimited JSON events in `streaming` format:
- `text` or `assistant` type → `ThinkingEvent`
- `tool_use` type → `ToolCallEvent` with `tool_id` and duration tracking
- `tool_result` type → `ToolResultEvent` with duration tracking
- `usage` type → `UsageEvent` with `input_tokens`, `output_tokens`, `cost_usd`

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

---
[← Auth and Quota](auth-quota.md) · [Home](index.md) · [Advanced Usage →](advanced.md)