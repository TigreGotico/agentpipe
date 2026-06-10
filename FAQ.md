# FAQ - agentpipe

## Antigravity Provider (`agy`)

### How does the Antigravity provider work?
The `antigravity` provider wraps the `agy` command-line interface. It runs `agy` in non-interactive print mode by passing the `--print` (or `-p`) flag along with the prompt.

### How does the provider manage sessions?
Unlike providers that output structured JSON (which includes session details), `agy` prints plaintext responses.
However, `agy` logs details such as when a new conversation is created to its logs. By specifying a unique log path per execution via the `--log-file` option, the `AntigravityProvider` can inspect that log file post-run to parse and extract the newly created `conversationID`.
To resume a session/conversation, the provider passes the `--conversation <id>` option if a `session_id` is supplied, or `--continue` if `continue_last` is enabled.

### What models does the provider support?
The `antigravity` provider queries the CLI to retrieve the list of available models. Standard registered model aliases are:
- `antigravity-flash-medium` -> `Gemini 3.5 Flash (Medium)` (Default)
- `antigravity-flash-high` -> `Gemini 3.5 Flash (High)`
- `antigravity-flash-low` -> `Gemini 3.5 Flash (Low)`
- `antigravity-pro-low` -> `Gemini 3.1 Pro (Low)`
- `antigravity-pro-high` -> `Gemini 3.1 Pro (High)`
- `antigravity-claude-sonnet` -> `Claude Sonnet 4.6 (Thinking)`
- `antigravity-claude-opus` -> `Claude Opus 4.6 (Thinking)`
- `antigravity-gpt-oss` -> `GPT-OSS 120B (Medium)`

### How is authentication status verified?
Authentication is verified by checking if running `agy models` completes successfully within a short timeout.
