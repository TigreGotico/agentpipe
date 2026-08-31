# A Free OpenAI-Compatible Endpoint

This page takes you from nothing to an HTTP endpoint that speaks the OpenAI
API and costs nothing to run. It is the deployment agentpipe was built for:
the free tiers of coding agent CLIs, wrapped in a chat API, so anything that
already talks to OpenAI can talk to them.

Everything below was run as written. Where output is shown, that is the real
output.

## What this is

agentpipe runs a coding agent CLI as a subprocess and turns its output into a
chat completion. The CLIs it wraps — OpenCode, Kilo Code, Gemini CLI and the
rest — all have free tiers, and most of them need no account and no credit
card. The server puts `/v1/chat/completions` in front of them.

## What this is not

It is not an inference server. There is no model in the container: every
request shells out to a CLI, which calls the vendor's API. If that vendor is
down, rate-limited, or has changed its free tier, so are you.

It is not fast. A free-tier coding agent takes seconds, not milliseconds, and
sends a large system prompt of its own before your prompt ever arrives. Expect
several thousand prompt tokens on a one-line question.

It is not a private endpoint. Your prompts go to whichever vendor serves the
model you named. Free tiers are usually free because of that.

And it is not a place to run untrusted prompts against your own files. The
CLIs behind it can read and write. Keep reading the "Locking it down" section
before you point anything public at it.

## Step 1: run the server

Pull the published image and run it:

```bash
docker run -d --name agentpipe -p 8000:8000 \
  -e AGENTPIPE_STATELESS=1 \
  ghcr.io/tigregotico/agentpipe:latest
```

The container prints what it found on startup:

```
=== agentpipe server ===

Provider CLIs:
  [OK]   kilo (7.4.21)
  [OK]   opencode (1.18.16)
  [MISS] claude
  [OK]   gemini (0.55.1)
  [OK]   aider (aider 0.86.2)
  [OK]   vibe (vibe 2.24.1)
  [OK]   qodercli (1.1.19)

Auth:
  [INFO] OPENROUTER_API_KEY not set — kilo/opencode use free-tier models without it

Starting server...
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Six CLIs are in the image. `claude` is not, because its installer is gated and
it needs a paid Anthropic subscription anyway. `agy` (Antigravity) and `mimo`
are not either; agentpipe supports them, but you have to install those CLIs
yourself.

Check it is alive:

```bash
curl -s http://localhost:8000/health
```

```json
{"status":"ok","agents":0}
```

## Step 2: ask it something

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "opencode/big-pickle",
       "messages": [{"role": "user", "content": "Reply with exactly: hello from agentpipe"}]}'
```

```json
{"id":"chatcmpl-ses_0028e85dfffeTK88PEjQI41pbe","object":"chat.completion",
 "created":1786663502,"model":"opencode/big-pickle",
 "choices":[{"index":0,"message":{"role":"assistant","content":"hello from agentpipe"},
             "finish_reason":"stop"}],
 "usage":{"prompt_tokens":7856,"completion_tokens":17,"total_tokens":7873}}
```

That is the whole thing. No API key was set, no account was created, and the
answer cost nothing. Note the 7856 prompt tokens for a one-line question: that
is the CLI's own system prompt, and it is why free tiers are the only sensible
place to run this.

The `model` field names the provider before the slash and the model after it.
`opencode/big-pickle`, `opencode/deepseek-v4-flash-free` and
`kilo/kilo-auto/free` all cost nothing. See
[Providers and Models](providers.md) for the full list.

## Step 3: use it with an OpenAI client

Nothing above is curl-specific. Point any OpenAI SDK at it:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="unused")
answer = client.chat.completions.create(
    model="opencode/big-pickle",
    messages=[{"role": "user", "content": "Name three sorting algorithms"}],
)
print(answer.choices[0].message.content)
```

`api_key` is ignored unless you set `AGENTPIPE_API_KEY` on the server. Most
clients refuse to send a request without one, so pass anything.

## Compose file

The same thing as a compose file, ready to `docker compose up -d`. This is
`docker-compose.stateless.yml` in the repository:

```yaml
services:
  agentpipe:
    image: ghcr.io/tigregotico/agentpipe:latest
    container_name: agentpipe
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      AGENTPIPE_STATELESS: "1"
      AGENTPIPE_MAX_CONCURRENCY: "4"
    tmpfs:
      - /root/.local/share/opencode
      - /root/.config/opencode
      - /root/.local/state
      - /root/.cache
      - /tmp:size=256m
    mem_limit: 4g
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    pids_limit: 256
```

## Stateless or stateful

`AGENTPIPE_STATELESS=1` is the setting that matters most, and the guide above
sets it. Without it, a request that carries no `user` field is keyed to an
agent named after the model, and that agent resumes its previous session. Two
strangers asking questions at the same time land in one conversation and read
each other's history.

So:

- Serving more than one person, or anything public: set it. History is the
  client's job, and every OpenAI client already sends the whole message list
  back on each turn.
- Working alone on your own project and wanting the agent to remember the
  repository between calls: leave it off, and pass a distinct `user` per
  caller.

Stateless mode also drops the per-agent lock, so `AGENTPIPE_MAX_CONCURRENCY`
(default 4) is what stops a burst of requests from starting a CLI subprocess
each.

## Behind ovos-persona-server

agentpipe answers on the OpenAI API, and ovos-persona-server speaks the OpenAI
API to whatever it is pointed at, so the two stack directly. The result is one
OpenAI endpoint per persona, each with its own model and system prompt, backed
by free coding agents.

A persona is a JSON file:

```json
{
  "name": "deepseek-v4-flash-free",
  "solvers": ["ovos-chat-openai-plugin"],
  "ovos-chat-openai-plugin": {
    "api_url": "http://agentpipe:8000/v1",
    "key": "unused",
    "model": "opencode/deepseek-v4-flash-free",
    "system_prompt": "You are the OpenVoiceOS assistant. Answer briefly and factually, in at most fifty words, and do not use emojis."
  }
}
```

Drop one file per model into `./personas`. ovos-persona-server has no
published image yet, so build it from the alphas with a small
`./persona/Dockerfile`:

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir "ovos-persona>=0.9.0a9" "ovos-openai-plugin>=2.0.8a2"
RUN pip install --no-cache-dir "ovos-persona-server>=0.17.0a1"
EXPOSE 8337
ENTRYPOINT ["ovos-persona-server"]
```

Then run the two together:

```yaml
services:
  agentpipe:
    image: ghcr.io/tigregotico/agentpipe:latest
    container_name: agentpipe
    restart: unless-stopped
    environment:
      AGENTPIPE_STATELESS: "1"
    tmpfs:
      - /root/.local/share/opencode
      - /root/.config/opencode
      - /root/.local/state
      - /root/.cache
      - /tmp:size=256m
    mem_limit: 4g
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    pids_limit: 256
    expose:
      - "8000"

  persona:
    build: ./persona
    restart: unless-stopped
    depends_on:
      - agentpipe
    volumes:
      - ./personas:/personas:ro
    ports:
      - "8337:8337"
    command: ["--personas-dir", "/personas",
              "--default-persona", "deepseek-v4-flash-free",
              "--host", "0.0.0.0", "--port", "8337"]
```

agentpipe is not published on the host here: only the persona server is. That
is deliberate. Persona files are the only way in, so a caller picks a persona
by name and cannot name an arbitrary model or reach agentpipe's native agent
API.

Callers then use the persona name as the model:

```bash
curl -s http://localhost:8337/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "deepseek-v4-flash-free",
       "messages": [{"role": "user", "content": "What is the capital of Portugal?"}]}'
```

```json
{"id":"chatcmpl-B1zvPJpmhRwDRe0kuTH9DkmOb7kQ",
 "choices":[{"finish_reason":"stop","index":0,
             "message":{"role":"assistant","content":"Lisbon is the capital of Portugal."}}],
 "model":"deepseek-v4-flash-free","object":"chat.completion",
 "usage":{"prompt_tokens":25,"completion_tokens":6,"total_tokens":31}}
```

For OVOS itself, point the chat plugin at the persona server and you have a
free assistant backend.

## Locking it down

The provider CLIs can read and write files and run shell commands. They are
programs driven by whatever prompt arrives. The server asks them to stay
behind their own permission prompts, but the container is what actually bounds
the damage, and the compose file above is the bounding:

- `read_only: true` with `tmpfs` mounts for the few paths the CLIs write to.
  Nothing survives a restart, including OpenCode's SQLite conversation history.
- No host mounts. No project directory, no login state. Free-tier models need
  no credentials, so there is nothing to persist.
- `cap_drop: ALL`, `no-new-privileges`, a pid cap and a memory cap.

If you expose agentpipe directly rather than through a persona server, set
`AGENTPIPE_API_KEY` to a real value and require it. Do not point a public
endpoint at a container that has your project mounted.

## Troubleshooting

**Every request returns `401 Invalid or missing API key` and you set no key.**
`AGENTPIPE_API_KEY` was passed as an empty string rather than left unset. A
compose line like `AGENTPIPE_API_KEY: "${AGENTPIPE_API_KEY:-}"` does exactly
that when the variable is not in your environment. Remove the line, or set a
real key and send it. Confirm with `docker exec <container> env | grep AGENT`.

**`Agent process exited with code 1`.** The CLI ran and failed. Read the rest
of the message; the CLI's own error is in there. The usual causes are a model
name the provider does not serve, an exhausted free tier, or the vendor being
down. Try the same prompt with `opencode/big-pickle`, which needs nothing.

**A provider you asked for is not in the container.** The startup log lists
every CLI as `[OK]` or `[MISS]`. `claude` is always `[MISS]` in the published
image. Install it inside a container of your own with
`npm install -g @anthropic-ai/claude-code`, or build a derived image.

**Two callers see each other's conversation.** `AGENTPIPE_STATELESS` is not
set. See the section above.

**It is slow.** It is a coding agent. A free-tier model on a one-line question
takes a few seconds and often longer. Raise `AGENTPIPE_MAX_CONCURRENCY` if the
requests are queueing rather than running, but the vendor's rate limit is the
real ceiling.

## Building it yourself

Contributors and anyone who wants a CLI the published image does not carry can
build from a checkout:

```bash
git clone https://github.com/TigreGotico/agentpipe
cd agentpipe
docker build -t agentpipe:local .
```

The published image is built from `dev` on every push, so a local build is
only needed for unreleased changes or a modified `Dockerfile`.

---
[← HTTP Server](server.md) · [Home](index.md) · [Providers and Models →](providers.md)
