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
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from agentpipe import Agent, GenerationResult
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


@dataclass
class _ManagedAgent:
    agent: Agent
    session_id: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_agents: dict[str, _ManagedAgent] = {}
_MAX_AGENTS = 100


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
        kwargs["cwd"] = cfg.cwd
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


@app.post("/agents")
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


@app.get("/agents")
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


@app.get("/agents/{name}")
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


@app.delete("/agents/{name}")
async def delete_agent(name: str) -> dict:
    ma = _agents.pop(name, None)
    if not ma:
        raise HTTPException(404, f"Agent '{name}' not found")
    logger.info("Deleted agent '%s'", name)
    return {"status": "deleted", "name": name}


@app.post("/agents/{name}/generate")
async def generate(name: str, req: GenerateRequest) -> GenerateResponse:
    ma = _agents.get(name)
    if not ma:
        raise HTTPException(404, f"Agent '{name}' not found")

    async with ma.lock:
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
            raise HTTPException(500, str(e)) from e


@app.post("/agents/{name}/generate-stream")
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
            except Exception as e:
                yield {"event": "error", "data": json.dumps({"error": str(e)})}

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


@app.get("/agents/{name}/session")
async def get_session(name: str) -> dict:
    ma = _agents.get(name)
    if not ma:
        raise HTTPException(404, f"Agent '{name}' not found")
    return {"name": name, "session_id": ma.session_id}


def _model_to_provider(model: str) -> str:
    prefix = model.split("/")[0].lower()
    known: dict[str, str] = {
        "aider": "aider",
        "claude": "claude",
        "gemini": "gemini",
        "kilo": "kilo",
        "opencode": "opencode",
        "qoder": "qoder",
        "vibe": "vibe",
    }
    return known.get(prefix, "kilo")


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


@app.post("/v1/chat/completions")
async def openai_chat_completions(body: dict):
    model = body.get("model", "kilo/kilo-auto/free")
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    user_id = body.get("user", "")

    agent_name = user_id or model.replace("/", "-").replace(":", "-")
    provider = _model_to_provider(model)

    if agent_name not in _agents:
        if len(_agents) >= _MAX_AGENTS:
            raise HTTPException(503, "Agent store full")
        _agents[agent_name] = _ManagedAgent(agent=Agent(provider, model=model))
        logger.info("Auto-created agent '%s' from model '%s'", agent_name, model)

    ma = _agents[agent_name]
    prompt = _messages_to_prompt(messages)

    if stream:
        return await _openai_stream(ma, prompt, model)
    return await _openai_complete(ma, prompt, model)


async def _openai_complete(ma: _ManagedAgent, prompt: str, model: str) -> dict:
    async with ma.lock:
        try:
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

    async def event_generator():
        async with ma.lock:
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
            except Exception as e:
                logger.exception("Stream failed")
                yield {"event": "data", "data": json.dumps({"error": str(e)})}

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
  POST /v1/chat/completions             OpenAI-compatible endpoint
  GET  /health                          Health check

OpenAI-compatible endpoint — point any OpenAI client at this server:
  curl http://localhost:8000/v1/chat/completions \\
    -H 'Content-Type: application/json' \\
    -d '{"model":"kilo/kilo-auto/free","messages":[{"role":"user","content":"Hello"}]}'

  Use the model name as provider/model. The model prefix determines the
  provider (kilo/, claude/, gemini/, opencode/, aider/, etc.). Agents
  are auto-created and sessions persist via the 'user' field.

Examples:
  curl -X POST http://localhost:8000/agents \\
    -H 'Content-Type: application/json' \\
    -d '{"name":"writer","provider":"kilo"}'

  curl -X POST http://localhost:8000/agents/writer/generate \\
    -H 'Content-Type: application/json' \\
    -d '{"prompt":"Write a unit test for this function"}'
"""
