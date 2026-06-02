# HTTP Server (FastAPI)

Run agentpipe agents behind HTTP with persistent sessions. Includes an
OpenAI-compatible `/v1/chat/completions` endpoint so any OpenAI client
can be pointed at this server.

## Quick Start

```bash
pip install agentpipe fastapi uvicorn sse-starlette
python -m agentpipe.server
```

The server starts on `http://localhost:8000`.

## OpenAI-Compatible Endpoint

Works with any OpenAI SDK, Cursor, Continue.dev, or `curl`:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"kilo/kilo-auto/free","messages":[{"role":"user","content":"Write a poem"}]}'
```

**Model naming convention:** the prefix after the first `/` selects the provider:

| Model | Provider |
|---|---|
| `kilo/kilo-auto/free` | Kilo Code (free) |
| `opencode/big-pickle` | OpenCode (free) |
| `claude/sonnet` | Claude Code |
| `gemini/gemini-2.5-flash` | Gemini CLI |
| `aider/...` | Aider |
| `vibe/...` | Mistral Vibe |

Agents are auto-created from the model name. Sessions persist — use the
`user` field to control session identity for multi-turn conversations.

### Streaming

```bash
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"kilo/kilo-auto/free","messages":[{"role":"user","content":"Write code"}],"stream":true}'
```

Returns OpenAI-compatible SSE chunks with `[DONE]` termination.

## Native API — Persistent Sessions

Create named agents with specific configuration, then send prompts.
Sessions persist across requests automatically.

### Create an Agent

```bash
curl -X POST http://localhost:8000/agents \
  -H 'Content-Type: application/json' \
  -d '{"name":"my-agent","provider":"kilo","config":{"timeout":120}}'
```

Response includes the agent name, provider, and model.

### Generate

```bash
curl -X POST http://localhost:8000/agents/my-agent/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Write unit tests for src/parser.py"}'
```

Returns the text response with token usage and session ID.

### Stream Events

```bash
curl -X POST http://localhost:8000/agents/my-agent/generate-stream \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Explain this code"}'
```

Returns SSE events: `thinking`, `tool_call`, `tool_result`, `usage`.

### List Agents

```bash
curl http://localhost:8000/agents
```

### Get Agent Info

```bash
curl http://localhost:8000/agents/my-agent
```

### Get Session Status

```bash
curl http://localhost:8000/agents/my-agent/session
```

### Delete Agent

```bash
curl -X DELETE http://localhost:8000/agents/my-agent
```

### Health

```bash
curl http://localhost:8000/health
```

## Docker

```bash
docker compose up
```

Pass API keys via environment:

```bash
OPENROUTER_API_KEY=sk-xxx ANTHROPIC_API_KEY=sk-ant-xxx docker compose up
```

The Docker image includes agentpipe, FastAPI, uvicorn, and sse-starlette.
Provider CLIs are not included — the Docker container delegates to the
host's installed CLIs via the mounted `/tmp` volume, or you can extend
the Dockerfile to install them.

## Configuration Fields

When creating an agent via the native API, the `AgentConfig` object supports:

| Field | Type | Default | Description |
|---|---|---|---|
| `provider` | str | (required) | Provider key (kilo, claude, gemini, ...) |
| `model` | str | None | Model override |
| `timeout` | int | 300 | Request timeout in seconds |
| `cwd` | str | /tmp | Working directory |
| `approval_mode` | str | None | default, yolo, plan, bypass |
| `sandbox` | bool | false | Sandbox mode |
| `files` | list[str] | None | File attachments |
| `include_dirs` | list[str] | None | Include directories |
| `system_prompt` | str | None | System prompt |
| `allowed_tools` | list[str] | None | Tool allow list |
| `disallowed_tools` | list[str] | None | Tool deny list |
| `effort` | str | None | Effort level (low, medium, high) |
