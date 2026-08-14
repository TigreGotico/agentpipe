"""The OpenAI-compatible streaming route must send a terminal finish_reason.

Strict OpenAI-compatible clients wait for a chunk whose finish_reason is not
null before treating the stream as complete. Before this fix the route sent
exactly one content chunk with finish_reason: null and then jumped straight
to [DONE], which is not a valid terminal state per the OpenAI contract.
"""
import json

import pytest

pytest.importorskip("fastapi")

import sys
import importlib


def _load_server(monkeypatch):
    for key in ("AGENTPIPE_STATELESS", "AGENTPIPE_OPENAI_APPROVAL",
                "AGENTPIPE_MAX_CONCURRENCY", "AGENTPIPE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    sys.modules.pop("agentpipe.server", None)
    return importlib.import_module("agentpipe.server")


class _FakeSession:
    """Stands in for AgentSession: yields one ThinkingEvent, no more."""

    session_id = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def generate_stream(self, prompt):
        from agentpipe._types import ThinkingEvent
        yield ThinkingEvent(text="hello world")


class _FakeAgent:
    continue_last = False

    def session(self):
        return _FakeSession()


class _FakeManagedAgent:
    def __init__(self):
        import asyncio
        self.agent = _FakeAgent()
        self.lock = asyncio.Lock()
        self.session_id = None
        self.last_used = 0.0


async def _collect_sse_chunks(response):
    chunks = []
    async for item in response.body_iterator:
        data = item["data"] if isinstance(item, dict) else item
        chunks.append(data)
    return chunks


class TestStreamingEmitsATerminalFinishReason:
    async def test_last_data_chunk_before_done_has_finish_reason_stop(self, monkeypatch):
        server = _load_server(monkeypatch)
        ma = _FakeManagedAgent()
        response = await server._openai_stream(ma, "hi", "kilo/kilo-auto/free")
        chunks = await _collect_sse_chunks(response)

        assert chunks[-1] == "[DONE]"
        # The chunk immediately preceding [DONE] must carry a real
        # finish_reason so strict parsers know the stream is complete.
        last_data = json.loads(chunks[-2])
        finish_reason = last_data["choices"][0]["finish_reason"]
        assert finish_reason == "stop", (
            f"expected terminal finish_reason 'stop', got {finish_reason!r} "
            f"in last chunk before [DONE]: {chunks}"
        )
