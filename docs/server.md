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

Agents are auto-created from the model name. Sessions persist. Use the
`user` field to control session identity for multi-turn conversations.

This surface is a chat endpoint, so its agents are built with the `default`
approval mode and the provider CLIs' file and shell tools stay behind their own
permission prompts, which a non-interactive run cannot answer. Set
`AGENTPIPE_OPENAI_APPROVAL=bypass` for a deployment that wants those tools
reachable from a request body.

### Stateless mode

Session identity defaults to the `user` field, and falls back to the model name
when a request does not send one. On a server that answers more than one
person, that fallback puts every such request on a single agent, which resumes
its previous session — so one caller's conversation reaches another's.

Set `AGENTPIPE_STATELESS=1` for a shared or public deployment. Each request
then gets its own agent, no session is ever resumed, and nothing is kept once
the response is written. Conversation history belongs to the client, which
sends it back as messages, the way the OpenAI API defines it.

```bash
AGENTPIPE_STATELESS=1 uvicorn agentpipe.server:app --host 0.0.0.0 --port 8000
```

Stateless mode governs the OpenAI surface only. The native `/agents/*`
endpoints work with agents an operator created by name, whose sessions are the
point, and they keep them.

It also does without the per-agent lock that serializes the default mode, so
`AGENTPIPE_MAX_CONCURRENCY` (default 4) bounds how many provider subprocesses
may run at once.

The provider CLIs keep their own records: opencode writes every conversation to
a SQLite database under `~/.local/share/opencode`. Stateless mode governs
agentpipe, not the CLI's own store, so a deployment that must keep history off
disk backs those directories with memory as well. `docker-compose.stateless.yml`
does both, and mounts nothing from the host:

```bash
docker compose -f docker-compose.stateless.yml up -d
```

### Streaming

```bash
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"kilo/kilo-auto/free","messages":[{"role":"user","content":"Write code"}],"stream":true}'
```

Returns OpenAI-compatible SSE chunks with `[DONE]` termination.

## Native API: Persistent Sessions

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

The image is published at `ghcr.io/tigregotico/agentpipe:latest`, built from
`dev` on every push. It bundles 6 provider CLIs (kilo, opencode, gemini, aider,
vibe, qodercli). Each works without any auth setup for its free-tier models.
Claude Code is not pre-installed. See the manual install steps below. On
startup, the container checks what is available and what auth is configured.

For the guided version of everything here, including running behind
ovos-persona-server, read
[A Free OpenAI-Compatible Endpoint](free-llm-endpoint.md).

### Quick start

```bash
docker run -d --name agentpipe -p 8000:8000 \
  -e AGENTPIPE_STATELESS=1 \
  ghcr.io/tigregotico/agentpipe:latest
```

Or with the workstation compose file, which mounts your project and your CLI
logins. API keys are optional — free-tier kilo and opencode need none:

```bash
echo "OPENROUTER_API_KEY=sk-or-v1-..." > .env   # optional
docker compose up
```

### Free-tier: no auth needed

`kilo` and `opencode` work immediately with their free-tier default
models (`kilo/kilo-auto/free` and `opencode/big-pickle`). They need no
API keys and no accounts. Run `docker compose up` and use them.

### API keys

Keys can be set via environment variables (in a `.env` file or shell):

| Variable | Providers | Required? |
|----------|-----------|-----------|
| `OPENROUTER_API_KEY` | aider, kilo, opencode (free models) | Recommended |
| `ANTHROPIC_API_KEY` | claude | For Claude |
| `OPENAI_API_KEY` | qoder, aider | Optional |
| `MISTRAL_API_KEY` | vibe | For Mistral Vibe |

### Auth persistence (optional)

Only needed if you want to use authenticated/pro features. Free-tier
models on kilo/opencode work without any of this.

CLI auth state can be persisted by mounting host directories into the
container:

| Host path | Container path | Provider |
|-----------|---------------|----------|
| `~/.local/share/kilo/` | `/root/.local/share/kilo/` | Kilo Code |
| `~/.config/opencode/` | `/root/.config/opencode/` | OpenCode |
| `~/.claude/` | `/root/.claude/` | Claude Code |
| `~/.config/gemini/` | `/root/.config/gemini/` | Gemini CLI |
| `~/.vibe/` | `/root/.vibe/` | Mistral Vibe |

To run interactive auth setup:

```bash
docker compose run --rm agentpipe kilo auth login
```

Claude Code is not in the image, so `claude auth login` only works after the
manual install below.

### Claude Code (manual install)

Claude Code requires a Cloudflare-gated installer and Anthropic auth,
so it's not pre-installed. To add it:

```bash
# Run the installer inside the container
docker compose run --rm agentpipe bash -c "curl -fsSL https://claude.ai/install | bash"

# Then authenticate
docker compose run --rm agentpipe claude auth login
```

The `~/.claude/` mount in `docker-compose.yml` persists the session.

### Working directory

Your current directory is mounted at `/workspace` inside the container.
Set `AGENTPIPE_CWD=/workspace` to have agents operate on your project files.

### Build locally

Only needed for unreleased changes or a modified `Dockerfile`. Uncomment the
`build: .` line in the compose file, then:

```bash
docker compose build
docker compose up
```

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

---
[← Model Cascade](cascade.md) · [Home](index.md) · [MCP and Approval Modes →](mcp-approval.md)
