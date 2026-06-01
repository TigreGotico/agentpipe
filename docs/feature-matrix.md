# Feature Matrix

| Feature | Claude | Gemini | OpenCode |
|---------|--------|--------|----------|
| **MCP servers** | Runtime (`--mcp-config`) | Config only | Config only |
| **Approval modes** | `--permission-mode` / `--dangerously-skip-permissions` | `--yolo` | Config only |
| **Budget cap** | `--max-budget-usd` | — | — |
| **Session resume** | `--resume <id>` | `--resume <id>` | `--session <id>` |
| **Stream format** | `stream-json` | `stream-json` | `--format=json` |
| **List sessions** | — | `--list-sessions` | `opencode session list` |
| **List models** | — | — | `opencode models` |
| **Auth status** | `claude auth status --json` | CLI check | `opencode providers list` |
| **Stats** | Per-invocation | Per-invocation | `opencode stats` |
| **Plan variants** | Sonnet / Haiku / Opus | Flash / Pro | Free / Zen / Go |
| **Cost tracking** | `total_cost_usd` in event | — | `cost` in `step_finish` |
| **Tool use events** | `ToolCallEvent` with `tool_id` | `ToolCallEvent` with `tool_id` | `ToolCallEvent` |
| **Tool result events** | `ToolResultEvent` | `ToolResultEvent` with `duration_ms` | `ToolResultEvent` |
| **Cache tokens** | `cache_read`/`cache_write` | — | `cache.read`/`cache.write` |

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

## Claude Approval Modes

| ApprovalMode | CLI Flag | Behavior |
|---|---|---|
| `DEFAULT` | `--dangerously-skip-permissions` | Full auto-approve |
| `AUTO_EDIT` | `--permission-mode acceptEdits` | Auto-approve edits, prompt for shell |
| `YOLO` | `--dangerously-skip-permissions` | Bypass all permissions |
| `PLAN` | `--permission-mode plan` | Read-only, no tool execution |
| `BYPASS` | `--dangerously-skip-permissions` | Same as YOLO |