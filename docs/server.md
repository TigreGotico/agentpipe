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

Every request is independent, the way the OpenAI API defines it: it gets its
own agent, resumes nothing, and leaves nothing behind. Send the `user` field to
opt into a server-side session — requests that carry the same `user` share one
agent and one conversation, so a multi-turn client can leave history out of the
request body.

The part before the first slash names the provider. It is removed before the
CLI sees the model unless it is a namespace the provider uses itself, so
`aider/openrouter/google/...` reaches aider as `openrouter/google/...` while
`kilo/kilo-auto/free` reaches kilo unchanged.

When the provider fails, the response is an HTTP error. A failure is never
answered with 200 and the error text in the assistant message, which a client
would read as a real reply.

This surface is a chat endpoint, so its agents are built with the `default`
approval mode and the provider CLIs' file and shell tools stay behind their own
permission prompts, which a non-interactive run cannot answer. Set
`AGENTPIPE_OPENAI_APPROVAL=bypass` for a deployment that wants those tools
reachable from a request body.

### Stateless mode

A request that sends no `user` never has a session, so nothing is shared
between callers by default. `AGENTPIPE_STATELESS=1` goes one step further and
refuses to keep a session even for a request that does send `user`, for a
deployment that wants no server-side conversation history at all.

```bash
AGENTPIPE_STATELESS=1 uvicorn agentpipe.server:app --host 0.0.0.0 --port 8000
```

Stateless mode governs the OpenAI surface only. The native `/agents/*`
endpoints work with agents an operator created by name, whose sessions are the
point, and they keep them.

A per-request agent has no shared lock to serialize it, so
`AGENTPIPE_MAX_CONCURRENCY` (default 4) bounds how many provider subprocesses
may run at once. That bound is global and it now applies to every request
without a `user`, which is most traffic on a default server. Four such
requests can run at once and the fifth waits, where a server that kept one
agent per model used to run one per model in parallel. Raise
`AGENTPIPE_MAX_CONCURRENCY` if the box can afford more provider subprocesses
than that.

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

Returns OpenAI-compatible SSE chunks and always ends with a chunk carrying
`finish_reason: "stop"` right before `[DONE]`, so strict clients that wait
for a terminal `finish_reason` do not hang.

Whether the content arrives token-by-token depends on the underlying CLI.
`claude`, `gemini`, and `qoder` run with a streaming JSON output mode, so
agentpipe forwards their output as it is produced and you get real
incremental chunks. `aider`, `antigravity`, `kilo`, `mimocode`, `opencode`,
and `vibe` do not have a streaming CLI mode agentpipe can use, so their
answer arrives as a single content chunk once the CLI process finishes,
followed immediately by the terminal chunk. Both cases are valid
OpenAI-compatible streams; only the first group gives a latency benefit.

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

You can mount host login state into the container, or log in inside the
container and keep the result in a named volume. Exact paths per CLI, a
copy-pasteable compose snippet, and the security trade-off are in
**[Sharing Credentials with the Container](credentials.md)**.

To see what the running container has:

```bash
docker compose run --rm agentpipe python -m agentpipe.provision
```

To run interactive auth setup:

```bash
docker compose run --rm agentpipe kilo auth login
```

Claude Code is not in the image, so `claude auth login` only works after the
manual install below.

### Claude Code (manual install)

Claude Code needs an installer and Anthropic auth, so it's not
pre-installed. To add it:

```bash
# Run the installer inside the container
docker compose run --rm agentpipe bash -c "curl -fsSL https://claude.ai/install.sh | bash"

# Then authenticate
docker compose run --rm agentpipe claude auth login
```

The `~/.claude/` mount in `docker-compose.yml` persists the session. The
install itself does not survive a restart — bake it into your own image if
you need it permanently.

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
