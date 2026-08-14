# Feature Matrix

| Feature | Aider | Claude | Gemini | Kilo | OpenCode | QoderCLI | Vibe |
|---------|-------|--------|--------|------|----------|----------|------|
| **MCP servers** | n/a | Runtime (`--mcp-config`) | Config only | Config only | Config only | Runtime (`--mcp-config`) | Config only |
| **Approval modes** | `--yes-always` | `--permission-mode` / `--dangerously-skip-permissions` | `--approval-mode` / `--yolo` | `--auto` / `--dangerously-skip-permissions` | `--dangerously-skip-permissions` | `--permission-mode` / `--dangerously-skip-permissions` | `--agent` (default/plan/accept-edits/auto-approve) |
| **Budget cap** | n/a | `--max-budget-usd` | n/a | n/a | n/a | `--max-budget-usd` | n/a |
| **Session resume** | n/a | `--resume <id>` | `--resume <id>` | `--session <id>` | `--session <id>` | `--resume <id>` | `--resume <id>` |
| **Continue last** | n/a | `--continue` | n/a | `--continue` | `--continue` | `--continue` | `--continue` |
| **Fork session** | n/a | `--fork-session` | n/a | `--fork` | `--fork` | `--fork-session` | n/a |
| **Session name** | n/a | `--name` | n/a | `--title` | `--title` | `--name` | `--workdir` |
| **System prompt** | n/a | `--system-prompt` | n/a | n/a | n/a | `--system-prompt` | Config (`system_prompt_id`) |
| **Append system prompt** | n/a | `--append-system-prompt` | n/a | n/a | n/a | `--append-system-prompt` | Config |
| **Allowed tools** | n/a | `--allowedTools` | `--allowed-tools` | n/a | n/a | `--allowed-tools` | `--enabled-tools` |
| **Disallowed tools** | n/a | `--disallowedTools` | n/a | n/a | n/a | `--disallowed-tools` | `--disabled-tools` (config) |
| **Effort level** | `--reasoning-effort` | `--effort` | n/a | `--variant` | `--variant` | `--effort` | n/a |
| **Structured output** | n/a | `--json-schema` | n/a | n/a | n/a | `--json-schema` | n/a |
| **Fallback model** | `--weak-model` | `--fallback-model` | n/a | n/a | n/a | `--fallback-model` | n/a |
| **Agent selection** | n/a | `--agent` | n/a | `--agent` | `--agent` | `--agent` | `--agent` |
| **Sandbox** | n/a | `--sandbox` | `--sandbox` | `--sandbox` | `--sandbox` | `--sandbox` | n/a |
| **Raw output** | `--no-pretty` | no verbose | `--raw-output` | n/a | n/a | no verbose | n/a |
| **File attachments** | `--file` | `--file` | n/a | `--file` | `--file` | `--file` | n/a |
| **Include dirs** | `--read` | `--add-dir` | `--include-directories` | `--dir` | `--dir` | `--add-dir` | `--add-dir` |
| **Extensions** | n/a | n/a | `--extensions` | n/a | n/a | n/a | n/a |
| **Max turns** | n/a | n/a | n/a | n/a | n/a | `--max-turns` | `--max-turns` |
| **Max price** | n/a | n/a | n/a | n/a | n/a | n/a | `--max-price` |
| **Max tokens** | n/a | n/a | n/a | n/a | n/a | n/a | `--max-tokens` |
| **Stream format** | plain text | `stream-json` | `stream-json` | `--format=json` | `--format=json` | `stream-json` | `streaming` (NDJSON) |
| **List sessions** | n/a | n/a | `--list-sessions` | `kilo session list` | `opencode session list` | n/a | n/a |
| **List models** | `--list-models` | n/a | n/a | `kilo models` | `opencode models` | n/a | n/a |
| **Auth status** | OAuth | `claude auth status --json` | CLI check | `kilo auth list` | `opencode providers list` | `qodercli auth status --json` | `vibe --setup` |
| **Stats** | n/a | Per-invocation | Per-invocation | `kilo stats` | `opencode stats` | Per-invocation | n/a |
| **Plan variants** | n/a | Sonnet / Haiku / Opus | Flash / Pro | Free / BYOK | Free / Zen / Go | n/a | default / plan / accept-edits / auto-approve |
| **Cost tracking** | In `UsageEvent` | `total_cost_usd` in event | n/a | `cost` in `step_finish` | `cost` in `step_finish` | `total_cost_usd` in event | In `usage` event |
| **Tool use events** | n/a | `ToolCallEvent` with `tool_id` | `ToolCallEvent` with `tool_id` | `ToolCallEvent` | `ToolCallEvent` | `ToolCallEvent` with `tool_id` | `ToolCallEvent` with `tool_id` |
| **Tool result events** | n/a | `ToolResultEvent` | `ToolResultEvent` with `duration_ms` | `ToolResultEvent` | `ToolResultEvent` | `ToolResultEvent` | `ToolResultEvent` with `duration_ms` |
| **Cache tokens** | n/a | `cache_read`/`cache_write` | n/a | `cache.read`/`cache.write` | `cache.read`/`cache.write` | `cache_read`/`cache_write` | n/a |

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

---
[← Advanced Usage](advanced.md) · [Home](index.md) · [API Reference →](api-reference.md)