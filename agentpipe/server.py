"""FastAPI server — expose multiple agentpipe agents behind HTTP with persistent sessions.

Includes an OpenAI-compatible /v1/chat/completions endpoint so any OpenAI client
can be pointed at this server.

Usage:
    pip install fastapi uvicorn sse-starlette
    python -m agentpipe.server

Then:
    # Native API
    curl -X POST http://localhost:8000/agents -H 'Content-Type: application/json' \
      -d '{"name":"writer","provider":"kilo"}'
    curl -X POST http://localhost:8000/agents/writer/generate \
      -H 'Content-Type: application/json' -d '{"prompt":"Write a poem"}'

    # OpenAI-compatible — use with any OpenAI client
    curl http://localhost:8000/v1/chat/completions \
      -H 'Content-Type: application/json' \
      -d '{"model":"kilo/kilo-auto/free","messages":[{"role":"user","content":"Hello"}]}'
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator

from agentpipe import Agent, GenerationResult, ProviderOutputError
from agentpipe._agent import DEFAULT_MODELS, _PROVIDER_MAP
from agentpipe._types import AgentEvent, ThinkingEvent, ToolCallEvent, ToolResultEvent, UsageEvent

try:
    from sse_starlette.sse import EventSourceResponse
except ImportError:
    EventSourceResponse = None  # type: ignore[assignment]

logger = logging.getLogger("agentpipe.server")

app = FastAPI(
    title="agentpipe",
    description="HTTP interface for multi-agent delegation via agentpipe",
    version="0.2.0",
)

# --- Security: optional bearer-token auth via AGENTPIPE_API_KEY env var ---
# An empty value means "no key", not "the empty key". Compose files pass
# `AGENTPIPE_API_KEY: "${AGENTPIPE_API_KEY:-}"`, so an operator who sets no key
# gets an empty string here, and treating that as a real key rejected every
# request with 401 while the server looked healthy.
_API_KEY: str | None = os.environ.get("AGENTPIPE_API_KEY", "").strip() or None
_bearer_scheme = HTTPBearer(auto_error=False)
_bearer_dep = Depends(_bearer_scheme)

_MAX_PROMPT_LENGTH = int(os.environ.get("AGENTPIPE_MAX_PROMPT_LENGTH", "100000"))
_ALLOWED_CWD_BASE: str = os.environ.get("AGENTPIPE_CWD", "/tmp")


async def _require_auth(
    credentials: HTTPAuthorizationCredentials | None = _bearer_dep,
) -> None:
    if _API_KEY is None:
        return
    if credentials is None or credentials.credentials != _API_KEY:
        raise HTTPException(401, "Invalid or missing API key")


def _validate_cwd(cwd: str) -> str:
    """Resolve *cwd* and ensure it lives under the allowed base directory."""
    try:
        resolved = Path(cwd).resolve(strict=False)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, "Invalid working directory") from exc
    allowed = Path(_ALLOWED_CWD_BASE).resolve(strict=False)
    if not (resolved == allowed or allowed in resolved.parents):
        raise HTTPException(
            403,
            f"Working directory must be under {_ALLOWED_CWD_BASE}",
        )
    return str(resolved)


def _validate_prompt(prompt: str) -> str:
    if len(prompt) > _MAX_PROMPT_LENGTH:
        raise HTTPException(
            413,
            f"Prompt exceeds maximum length ({_MAX_PROMPT_LENGTH} chars)",
        )
    return prompt


@dataclass
class _ManagedAgent:
    agent: Agent
    session_id: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_used: float = field(default_factory=time.monotonic)


_agents: dict[str, _ManagedAgent] = {}
_MAX_AGENTS = 100
_AGENT_TTL_SECONDS = float(os.environ.get("AGENTPIPE_AGENT_TTL", "3600"))
# Refuse to keep a session even for a request that names a "user". The OpenAI
# surface isolates anonymous requests on its own (see openai_chat_completions),
# so this is for a deployment that wants no server-side history at all.
_STATELESS = os.environ.get("AGENTPIPE_STATELESS", "").strip().lower() in ("1", "true", "yes", "on")
# A per-request agent has no shared lock and does not count against _MAX_AGENTS,
# and those are what keep concurrent provider subprocesses bounded. This
# semaphore replaces them, so a burst of requests queues instead of starting a
# subprocess each.
_MAX_CONCURRENT = int(os.environ.get("AGENTPIPE_MAX_CONCURRENCY", "4"))
_stateless_slots = asyncio.Semaphore(_MAX_CONCURRENT)

# The OpenAI surface is a chat endpoint: it returns text and nothing else, so
# the provider CLIs' file and shell tools are not needed to serve it. Left
# unset, an approval mode of None is what makes the opencode provider ask for
# --dangerously-skip-permissions. DEFAULT keeps the tools behind the CLI's own
# permission prompts, which a non-interactive run cannot answer.
# Set AGENTPIPE_OPENAI_APPROVAL to override for a deployment that wants them.
from agentpipe._types import ApprovalMode

_OPENAI_APPROVAL = os.environ.get("AGENTPIPE_OPENAI_APPROVAL", "").strip().lower()


def _evict_stale_agents() -> None:
    """Remove agents that have been idle longer than the TTL."""
    now = time.monotonic()
    stale = [name for name, ma in _agents.items() if now - ma.last_used > _AGENT_TTL_SECONDS]
    for name in stale:
        _agents.pop(name, None)
        logger.info("Evicted idle agent '%s'", name)


class AgentConfig(BaseModel):
    provider: str
    model: str | None = None
    timeout: int = 300
    cwd: str = "/tmp"
    approval_mode: str | None = None
    sandbox: bool = False
    files: list[str] | None = None
    include_dirs: list[str] | None = None
    system_prompt: str | None = None
    allowed_tools: list[str] | None = None
    disallowed_tools: list[str] | None = None
    effort: str | None = None


class CreateAgentRequest(BaseModel):
    name: str | None = None
    provider: str
    model: str | None = None
    timeout: int = 300
    cwd: str = "/tmp"
    config: AgentConfig | None = None


class GenerateRequest(BaseModel):
    prompt: str
    stream: bool = False

    @field_validator("prompt")
    @classmethod
    def check_prompt_length(cls, v: str) -> str:
        if len(v) > _MAX_PROMPT_LENGTH:
            msg = f"Prompt exceeds maximum length ({_MAX_PROMPT_LENGTH} chars)"
            raise ValueError(msg)
        return v


class GenerateResponse(BaseModel):
    text: str
    session_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None


class AgentInfo(BaseModel):
    name: str
    provider: str
    model: str | None
    session_id: str | None
    timeout: int
    cwd: str


def _build_agent(name: str, req: CreateAgentRequest) -> Agent:
    cfg = req.config or AgentConfig(provider=req.provider)
    kwargs: dict[str, Any] = {}
    if cfg.model:
        kwargs["model"] = cfg.model
    if cfg.timeout:
        kwargs["timeout"] = cfg.timeout
    if cfg.cwd:
        kwargs["cwd"] = _validate_cwd(cfg.cwd)
    if cfg.approval_mode:
        from agentpipe._types import ApprovalMode

        kwargs["approval_mode"] = ApprovalMode(cfg.approval_mode)
    if cfg.sandbox:
        kwargs["sandbox"] = True
    if cfg.files:
        kwargs["files"] = cfg.files
    if cfg.include_dirs:
        kwargs["include_dirs"] = cfg.include_dirs
    if cfg.system_prompt:
        kwargs["system_prompt"] = cfg.system_prompt
    if cfg.allowed_tools:
        kwargs["allowed_tools"] = cfg.allowed_tools
    if cfg.disallowed_tools:
        kwargs["disallowed_tools"] = cfg.disallowed_tools
    if cfg.effort:
        from agentpipe._types import EffortLevel

        kwargs["effort"] = EffortLevel(cfg.effort)
    agent = Agent(cfg.provider, **kwargs)
    return agent


@app.post("/agents", dependencies=[Depends(_require_auth)])
async def create_agent(req: CreateAgentRequest) -> AgentInfo:
    name = req.name or f"agent-{uuid4().hex[:8]}"
    if name in _agents:
        raise HTTPException(409, f"Agent '{name}' already exists")
    if len(_agents) >= _MAX_AGENTS:
        raise HTTPException(503, "Agent store full")
    agent = _build_agent(name, req)
    _agents[name] = _ManagedAgent(agent=agent)
    logger.info("Created agent '%s' (provider=%s, model=%s)", name, req.provider, agent.model)
    return AgentInfo(
        name=name,
        provider=req.provider,
        model=agent.model,
        session_id=None,
        timeout=agent.timeout,
        cwd=agent.cwd,
    )


@app.get("/agents", dependencies=[Depends(_require_auth)])
async def list_agents() -> list[AgentInfo]:
    return [
        AgentInfo(
            name=name,
            provider=ma.agent.provider,
            model=ma.agent.model,
            session_id=ma.session_id,
            timeout=ma.agent.timeout,
            cwd=ma.agent.cwd,
        )
        for name, ma in _agents.items()
    ]


@app.get("/agents/{name}", dependencies=[Depends(_require_auth)])
async def get_agent(name: str) -> AgentInfo:
    ma = _agents.get(name)
    if not ma:
        raise HTTPException(404, f"Agent '{name}' not found")
    return AgentInfo(
        name=name,
        provider=ma.agent.provider,
        model=ma.agent.model,
        session_id=ma.session_id,
        timeout=ma.agent.timeout,
        cwd=ma.agent.cwd,
    )


@app.delete("/agents/{name}", dependencies=[Depends(_require_auth)])
async def delete_agent(name: str) -> dict:
    ma = _agents.pop(name, None)
    if not ma:
        raise HTTPException(404, f"Agent '{name}' not found")
    logger.info("Deleted agent '%s'", name)
    return {"status": "deleted", "name": name}


@app.post("/agents/{name}/generate", dependencies=[Depends(_require_auth)])
async def generate(name: str, req: GenerateRequest) -> GenerateResponse:
    ma = _agents.get(name)
    if not ma:
        raise HTTPException(404, f"Agent '{name}' not found")

    async with ma.lock:
        ma.last_used = time.monotonic()
        try:
            if ma.session_id:
                ma.agent.continue_last = True
            result: GenerationResult = await ma.agent.generate_full(req.prompt)
            if result.session_id:
                ma.session_id = result.session_id
            usage = result.usage
            return GenerateResponse(
                text=result.text,
                session_id=result.session_id,
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                cost_usd=usage.cost_usd if usage else None,
            )
        except Exception as e:
            logger.exception("Agent '%s' generate failed", name)
            raise HTTPException(500, "Agent generation failed") from e


@app.post("/agents/{name}/generate-stream", dependencies=[Depends(_require_auth)])
async def generate_stream(name: str, req: GenerateRequest):
    if EventSourceResponse is None:
        raise HTTPException(500, "sse-starlette not installed (pip install sse-starlette)")

    ma = _agents.get(name)
    if not ma:
        raise HTTPException(404, f"Agent '{name}' not found")

    async def event_generator():
        async with ma.lock:
            if ma.session_id:
                ma.agent.continue_last = True

            session = ma.agent.session()
            try:
                async with session as sess:
                    async for event in sess.generate_stream(req.prompt):
                        yield _serialize_event(event)
                    if sess.session_id:
                        ma.session_id = sess.session_id
            except Exception:
                logger.exception("Stream generation failed")
                yield {"event": "error", "data": json.dumps({"error": "Agent generation failed"})}

    return EventSourceResponse(event_generator())


def _serialize_event(event: AgentEvent) -> dict:
    data: dict[str, Any] = {}
    if isinstance(event, ThinkingEvent):
        data = {"type": "thinking", "text": event.text}
    elif isinstance(event, ToolCallEvent):
        data = {"type": "tool_call", "tool": event.tool, "args": str(event.args) if event.args else None}
    elif isinstance(event, ToolResultEvent):
        data = {"type": "tool_result", "tool": event.tool, "output": event.output[:500] if event.output else ""}
    elif isinstance(event, UsageEvent):
        data = {
            "type": "usage",
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
            "cost_usd": event.cost_usd,
        }
    else:
        data = {"type": "unknown", "raw": str(event)}
    return {"event": data["type"], "data": json.dumps(data)}


@app.get("/agents/{name}/session", dependencies=[Depends(_require_auth)])
async def get_session(name: str) -> dict:
    ma = _agents.get(name)
    if not ma:
        raise HTTPException(404, f"Agent '{name}' not found")
    return {"name": name, "session_id": ma.session_id}


# The OpenAI `model` field carries both the provider and the model, so the part
# before the first slash has to name a provider. These are the prefixes the
# provider CLIs actually emit in their own model strings.
_MODEL_PREFIXES: dict[str, str] = {
    "aider": "aider",
    "openrouter": "aider",
    "antigravity": "antigravity",
    "claude": "claude",
    "gemini": "gemini",
    "kilo": "kilo",
    "mimo": "mimo",
    "xiaomi": "mimo",
    "opencode": "opencode",
    "opencode-go": "opencode-go",
    "qoder": "qoder",
    "vibe": "vibe",
}

# How an operator installs each provider CLI, keyed by the binary name the
# provider actually execs. Used to make a missing-CLI 503 actionable instead
# of just naming what is absent. See docs/getting-started.md for the same
# table with auth steps.
_CLI_INSTALL_HINTS: dict[str, str] = {
    "aider": "pip install aider-chat",
    "claude": "curl -fsSL https://claude.ai/install.sh | bash",
    "gemini": "npm install -g @google/gemini-cli",
    "kilo": "npm install -g @kilocode/cli",
    "opencode": "npm install -g opencode",
    "qodercli": "npm install -g @qoder-ai/qodercli",
    "vibe": "pip install mistral-vibe",
}


def _missing_cli_message(binary_name: str) -> str:
    hint = _CLI_INSTALL_HINTS.get(binary_name)
    if hint:
        return (
            f"Provider CLI '{binary_name}' is not installed or not in PATH. "
            f"Install it with: {hint}"
        )
    return f"Provider CLI '{binary_name}' is not installed or not in PATH"


# The leading segment of every model the providers name themselves. A prefix
# in here belongs to the model; anything else only picked the provider and has
# to come off before the CLI sees it.
_MODEL_NAMESPACES: set[str] = {
    default.split("/")[0].lower() for default in DEFAULT_MODELS.values() if "/" in default
}


def _model_to_provider(model: str) -> str:
    """Name the provider that serves *model*, or refuse.

    A model this server cannot place used to fall through to kilo, which then
    failed inside the CLI with an error that named neither the model nor the
    provider. Refusing here says what went wrong.
    """
    return _route_model(model)[0]


def _route_model(model: str) -> tuple[str, str | None]:
    """Split *model* into the provider that serves it and the model it names.

    Some prefixes route and nothing more: "aider/" picks the provider, and the
    CLI behind it never heard of a model called "aider/something". Others are
    part of the name the CLI expects — kilo's own models really are called
    "kilo/...", and aider's are called "openrouter/...". The model namespaces
    the providers themselves use tell the two apart, so a new provider needs
    no extra table here.

    The returned model is None for a bare provider alias, which names no model
    and lets the provider choose its own default.
    """
    name = model.strip()
    if name in _PROVIDER_MAP:
        return name, None
    prefix = name.split("/")[0].lower()
    provider = _MODEL_PREFIXES.get(prefix)
    if provider is None:
        raise HTTPException(
            400,
            f"Unknown model '{model}'. Use one of the provider aliases "
            f"({', '.join(sorted(_PROVIDER_MAP))}) or a model whose prefix "
            f"names a provider ({', '.join(sorted(_MODEL_PREFIXES))}). "
            "GET /v1/models lists the defaults.",
        )
    if "/" in name and prefix not in _MODEL_NAMESPACES:
        return provider, name.split("/", 1)[1]
    return provider, name


def _messages_to_prompt(messages: list[dict]) -> str:
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            texts = [c["text"] for c in content if c.get("type") == "text"]
            content = "\n".join(texts)
        if role == "system":
            parts.append(f"System: {content}")
        elif role == "user":
            parts.append(f"User: {content}")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
    return "\n".join(parts)


def _build_openai_agent(provider: str, model: str | None) -> Agent:
    """Build the agent that serves one OpenAI-compatible request."""
    approval = ApprovalMode.DEFAULT
    if _OPENAI_APPROVAL:
        try:
            approval = ApprovalMode(_OPENAI_APPROVAL)
        except ValueError:
            logger.warning("AGENTPIPE_OPENAI_APPROVAL=%r is not an approval "
                           "mode; using %s", _OPENAI_APPROVAL, approval.value)
    return Agent(provider, model=model, approval_mode=approval)


@app.get("/v1/models", dependencies=[Depends(_require_auth)])
async def openai_models() -> dict:
    """List what the `model` field accepts, in the shape OpenAI clients expect.

    Each entry is a provider alias. Its default model is listed too, and either
    string is accepted as the `model` field.
    """
    created = int(time.time())
    data = []
    for alias in sorted(_PROVIDER_MAP):
        default = DEFAULT_MODELS.get(alias)
        data.append({"id": alias, "object": "model", "created": created,
                     "owned_by": "agentpipe", "default_model": default})
        if default and default != alias:
            data.append({"id": default, "object": "model", "created": created,
                         "owned_by": "agentpipe", "default_model": default})
    return {"object": "list", "data": data}


@app.post("/v1/chat/completions", dependencies=[Depends(_require_auth)])
async def openai_chat_completions(body: dict):
    model = body.get("model")
    if not model or not model.strip():
        raise HTTPException(
            400,
            "Missing or empty 'model' field. Use one of the provider aliases "
            f"({', '.join(sorted(_PROVIDER_MAP))}) or a model whose prefix "
            "names a provider. GET /v1/models lists the defaults.",
        )
    messages = body.get("messages")
    if not messages:
        raise HTTPException(
            400,
            "Missing or empty 'messages' field. Provide at least one message.",
        )
    stream = body.get("stream", False)
    user_id = body.get("user", "")

    prompt = _messages_to_prompt(messages)
    _validate_prompt(prompt)

    provider, model_arg = _route_model(model)

    # A chat completion is independent of every other one unless the caller
    # says otherwise, and the only way a caller says otherwise here is the
    # "user" field. Keying on the model string instead put every caller of
    # that model on one running conversation, and the answers bled across.
    if _STATELESS or not user_id:
        # Not stored in _agents: nothing to look up, nothing to continue, and
        # nothing left behind once the response is written. The shared slot
        # limit stands in for the per-agent lock this path does without.
        ma = _ManagedAgent(agent=_build_openai_agent(provider, model_arg),
                           lock=_stateless_slots)
    else:
        _evict_stale_agents()
        if user_id not in _agents:
            if len(_agents) >= _MAX_AGENTS:
                raise HTTPException(503, "Agent store full")
            _agents[user_id] = _ManagedAgent(
                agent=_build_openai_agent(provider, model_arg))
            logger.info("Auto-created agent '%s' from model '%s'", user_id, model)

        ma = _agents[user_id]
        ma.last_used = time.monotonic()

    if stream:
        return await _openai_stream(ma, prompt, model)
    return await _openai_complete(ma, prompt, model)


async def _openai_complete(ma: _ManagedAgent, prompt: str, model: str) -> dict:
    binary_name = ma.agent._provider_instance.binary_name
    import shutil

    if not shutil.which(binary_name):
        raise HTTPException(503, _missing_cli_message(binary_name))
    async with ma.lock:
        try:
            # A per-request agent is fresh, so it has no session and cannot
            # resume one. Only an agent kept for a named "user" ever does.
            if ma.session_id:
                ma.agent.continue_last = True
            result = await ma.agent.generate_full(prompt)
            if result.session_id:
                ma.session_id = result.session_id
        except Exception as e:
            logger.exception("OpenAI-compat completion failed for model '%s'", model)
            raise HTTPException(500, str(e)) from e

    usage = result.usage or UsageEvent()
    return {
        "id": f"chatcmpl-{result.session_id or uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.input_tokens,
            "completion_tokens": usage.output_tokens,
            "total_tokens": usage.input_tokens + usage.output_tokens,
        },
    }


async def _openai_stream(ma: _ManagedAgent, prompt: str, model: str):
    if EventSourceResponse is None:
        raise HTTPException(500, "sse-starlette not installed (pip install sse-starlette)")

    binary_name = ma.agent._provider_instance.binary_name
    import shutil

    if not shutil.which(binary_name):
        raise HTTPException(503, _missing_cli_message(binary_name))

    async def event_generator():
        async with ma.lock:
            # Same as the blocking path: only a "user"-keyed agent has a
            # session to continue.
            if ma.session_id:
                ma.agent.continue_last = True

            session = ma.agent.session()
            try:
                async with session as sess:
                    async for event in sess.generate_stream(prompt):
                        if isinstance(event, ThinkingEvent) and event.text:
                            chunk = {
                                "id": "chatcmpl-stream",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": model,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {"content": event.text},
                                        "finish_reason": None,
                                    }
                                ],
                            }
                            yield {"event": "data", "data": json.dumps(chunk)}
                    if sess.session_id:
                        ma.session_id = sess.session_id
                    final_chunk = {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                    yield {"event": "data", "data": json.dumps(final_chunk)}
            except Exception as e:
                logger.exception("OpenAI-compat stream failed")
                # "stop" here told every OpenAI client the answer finished
                # normally, and the extra "error" key is not part of the
                # schema so the SDKs drop it: a failure arrived as a short
                # but successful reply. The clients do read finish_reason,
                # and a provider failure is not a stop.
                detail = str(e) if isinstance(e, ProviderOutputError) \
                    else "Agent generation failed"
                error_chunk = {
                    "id": "chatcmpl-stream",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "error",
                        }
                    ],
                    "error": {"message": detail, "type": "provider_error"},
                }
                yield {"event": "data", "data": json.dumps(error_chunk)}

        yield {"event": "data", "data": "[DONE]"}

    return EventSourceResponse(event_generator())


@app.get("/health")
async def health():
    return {"status": "ok", "agents": len(_agents)}


@app.get("/", response_class=PlainTextResponse)
async def root():
    return """agentpipe server — Multi-agent HTTP API with OpenAI compatibility

Endpoints:
  POST /agents                          Create an agent
  GET  /agents                          List all agents
  GET  /agents/{name}                   Get agent info
  DELETE /agents/{name}                 Delete an agent
  POST /agents/{name}/generate          Send a prompt (blocking)
  POST /agents/{name}/generate-stream   Send a prompt (SSE stream)
  GET  /agents/{name}/session           Get session status
  GET  /v1/models                       OpenAI-compatible model list
  POST /v1/chat/completions             OpenAI-compatible endpoint
  GET  /health                          Health check

OpenAI-compatible endpoint — point any OpenAI client at this server:
  curl http://localhost:8000/v1/chat/completions \\
    -H 'Content-Type: application/json' \\
    -d '{"model":"kilo/kilo-auto/free","messages":[{"role":"user","content":"Hello"}]}'

  Use the model name as provider/model. The model prefix determines the
  provider (kilo/, claude/, gemini/, opencode/, aider/, etc.). Each
  request is independent; send a 'user' field to keep a session.

Examples:
  curl -X POST http://localhost:8000/agents \\
    -H 'Content-Type: application/json' \\
    -d '{"name":"writer","provider":"kilo"}'

  curl -X POST http://localhost:8000/agents/writer/generate \\
    -H 'Content-Type: application/json' \\
    -d '{"prompt":"Write a unit test for this function"}'
"""
