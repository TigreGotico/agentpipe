# Feature Matrix

| Feature | Aider | Claude | Gemini | Kilo | OpenCode | QoderCLI | Vibe |
|---------|-------|--------|--------|------|----------|----------|------|
| **MCP servers** | — | Runtime (`--mcp-config`) | Config only | Config only | Config only | Runtime (`--mcp-config`) | Config only |
| **Approval modes** | `--yes-always` | `--permission-mode` / `--dangerously-skip-permissions` | `--approval-mode` / `--yolo` | `--auto` / `--dangerously-skip-permissions` | `--dangerously-skip-permissions` | `--permission-mode` / `--dangerously-skip-permissions` | `--agent` (default/plan/accept-edits/auto-approve) |
| **Budget cap** | — | `--max-budget-usd` | — | — | — | `--max-budget-usd` | — |
| **Session resume** | — | `--resume <id>` | `--resume <id>` | `--session <id>` | `--session <id>` | `--resume <id>` | `--resume <id>` |
| **Continue last** | — | `--continue` | — | `--continue` | `--continue` | `--continue` | `--continue` |
| **Fork session** | — | `--fork-session` | — | `--fork` | `--fork` | `--fork-session` | — |
| **Session name** | — | `--name` | — | `--title` | `--title` | `--name` | `--workdir` |
| **System prompt** | — | `--system-prompt` | — | — | — | `--system-prompt` | Config (`system_prompt_id`) |
| **Append system prompt** | — | `--append-system-prompt` | — | — | — | `--append-system-prompt` | Config |
| **Allowed tools** | — | `--allowedTools` | `--allowed-tools` | — | — | `--allowed-tools` | `--enabled-tools` |
| **Disallowed tools** | — | `--disallowedTools` | — | — | — | `--disallowed-tools` | `--disabled-tools` (config) |
| **Effort level** | `--reasoning-effort` | `--effort` | — | `--variant` | `--variant` | `--effort` | — |
| **Structured output** | — | `--json-schema` | — | — | — | `--json-schema` | — |
| **Fallback model** | `--weak-model` | `--fallback-model` | — | — | — | `--fallback-model` | — |
| **Agent selection** | — | `--agent` | — | `--agent` | `--agent` | `--agent` | `--agent` |
| **Sandbox** | — | `--sandbox` | `--sandbox` | `--sandbox` | `--sandbox` | `--sandbox` | — |
| **Raw output** | `--no-pretty` | no verbose | `--raw-output` | — | — | no verbose | — |
| **File attachments** | `--file` | `--file` | — | `--file` | `--file` | `--file` | — |
| **Include dirs** | `--read` | `--add-dir` | `--include-directories` | `--dir` | `--dir` | `--add-dir` | `--add-dir` |
| **Extensions** | — | — | `--extensions` | — | — | — | — |
| **Max turns** | — | — | — | — | — | `--max-turns` | `--max-turns` |
| **Max price** | — | — | — | — | — | — | `--max-price` |
| **Max tokens** | — | — | — | — | — | — | `--max-tokens` |
| **Stream format** | plain text | `stream-json` | `stream-json` | `--format=json` | `--format=json` | `stream-json` | `streaming` (NDJSON) |
| **List sessions** | — | — | `--list-sessions` | `kilo session list` | `opencode session list` | — | — |
| **List models** | `--list-models` | — | — | `kilo models` | `opencode models` | — | — |
| **Auth status** | OAuth | `claude auth status --json` | CLI check | `kilo auth list` | `opencode providers list` | `qodercli auth status --json` | `vibe --setup` |
| **Stats** | — | Per-invocation | Per-invocation | `kilo stats` | `opencode stats` | Per-invocation | — |
| **Plan variants** | — | Sonnet / Haiku / Opus | Flash / Pro | Free / BYOK | Free / Zen / Go | — | default / plan / accept-edits / auto-approve |
| **Cost tracking** | In `UsageEvent` | `total_cost_usd` in event | — | `cost` in `step_finish` | `cost` in `step_finish` | `total_cost_usd` in event | In `usage` event |
| **Tool use events** | — | `ToolCallEvent` with `tool_id` | `ToolCallEvent` with `tool_id` | `ToolCallEvent` | `ToolCallEvent` | `ToolCallEvent` with `tool_id` | `ToolCallEvent` with `tool_id` |
| **Tool result events** | — | `ToolResultEvent` | `ToolResultEvent` with `duration_ms` | `ToolResultEvent` | `ToolResultEvent` | `ToolResultEvent` | `ToolResultEvent` with `duration_ms` |
| **Cache tokens** | — | `cache_read`/`cache_write` | — | `cache.read`/`cache.write` | `cache.read`/`cache.write` | `cache_read`/`cache_write` | — |

## OpenCode Plan Comparison

| | Free | Zen | Go |
|---|---|---|---|
| **Provider** | `opencode-free` | `opencode-zen` | `opencode-go` |
| **Endpoint** | `opencode.ai/zen/v1` | `opencode.ai/zen/v1` | `opencode.ai/zen/go/v1` |
| **Billing** | $0 | Pay-as-you-go | $5→$10/mo subscription |
| **Model prefix** | `opencode/` | `opencode/` | `opencode-go/` |
| **Default model** | `big-pickle` | `gemini-3-flash` | `deepseek-v4-flash` |
| **Free models** | Yes (big-pickle, *-free) | Yes (same free models) | Yes (200 req/5hr) |
| **Rate limits** | Standard | Standard | Per-model per 5hr |
| **Auth key** | Same as Zen | `opencode` slot in auth.json | `opencode-go` slot in auth.json |

## Approval Modes by Provider

### Claude

| ApprovalMode | CLI Flag | Behavior |
|---|---|---|
| `DEFAULT` | `--dangerously-skip-permissions` | Full auto-approve |
| `AUTO_EDIT` | `--permission-mode acceptEdits` | Auto-approve edits, prompt for shell |
| `YOLO` | `--dangerously-skip-permissions` | Bypass all permissions |
| `PLAN` | `--permission-mode plan` | Read-only, no tool execution |
| `BYPASS` | `--dangerously-skip-permissions` | Same as YOLO |

### Gemini

| ApprovalMode | CLI Flag | Behavior |
|---|---|---|
| `DEFAULT` | `--approval-mode default` | Prompt for approval |
| `AUTO_EDIT` | `--approval-mode auto_edit` | Auto-approve edits |
| `YOLO` | `--yolo` | Auto-approve all tools |
| `PLAN` | `--approval-mode plan` | Read-only mode |
| `BYPASS` | `--yolo` | Same as YOLO |

### OpenCode

| ApprovalMode | CLI Flag | Behavior |
|---|---|---|
| `DEFAULT` / `AUTO_EDIT` / `PLAN` | _no flag_ | Normal approval |
| `YOLO` / `BYPASS` | `--dangerously-skip-permissions` | Bypass all permissions |

## Effort Levels (Claude vs OpenCode)

| EffortLevel | Claude `--effort` | OpenCode `--variant` |
|---|---|---|
| `LOW` | `low` | `minimal` |
| `MEDIUM` | `medium` | `low` |
| `HIGH` | `high` | `high` |
| `VERY_HIGH` | `xhigh` | `max` |
| `MAX` | `max` | `max` |