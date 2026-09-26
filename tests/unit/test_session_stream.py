"""Tests for AgentSession.generate_stream and edge cases."""

from __future__ import annotations

import pytest

from agentpipe._session import AgentSession
from agentpipe._types import ThinkingEvent
from agentpipe.providers.claude import ClaudeProvider


class TestSessionGenerateStream:
    @pytest.mark.asyncio
    async def test_stream_yields_events(self):
        provider = ClaudeProvider()
        session = AgentSession(provider)

        async def mock_streaming(spec):
            yield ("stdout", '{"type":"assistant","content":[{"type":"text","text":"hi"}]}\n')
            yield ("stdout", '{"type":"result","result":"hi","usage":{"input_tokens":5,"output_tokens":3}}\n')

        session._executor.run_streaming = mock_streaming

        events = [event async for event in session.generate_stream("test")]

        assert len(events) >= 1
        assert any(isinstance(e, ThinkingEvent) for e in events)

    @pytest.mark.asyncio
    async def test_stream_extracts_session_id(self):
        provider = ClaudeProvider()
        session = AgentSession(provider)

        async def mock_streaming(spec):
            yield ("stdout", '{"type":"system","session_id":"stream-sess-1"}\n')
            yield ("stdout", '{"type":"assistant","content":[{"type":"text","text":"hello"}]}\n')

        session._executor.run_streaming = mock_streaming

        async for _ in session.generate_stream("test"):
            pass

        assert session.session_id == "stream-sess-1"

    @pytest.mark.asyncio
    async def test_stream_accumulates_usage(self):
        provider = ClaudeProvider()
        session = AgentSession(provider)

        async def mock_streaming(spec):
            yield ("stdout", '{"type":"result","result":"ok","usage":{"input_tokens":10,"output_tokens":5}}\n')

        session._executor.run_streaming = mock_streaming

        async for _event in session.generate_stream("test"):
            pass

        assert session.usage.total_input_tokens == 10
        assert session.usage.total_output_tokens == 5
        assert session.usage.turn_count == 1

    @pytest.mark.asyncio
    async def test_stream_skips_empty_lines(self):
        provider = ClaudeProvider()
        session = AgentSession(provider)

        async def mock_streaming(spec):
            yield ("stdout", "\n")
            yield ("stdout", "   \n")
            yield ("stdout", '{"type":"assistant","content":[{"type":"text","text":"x"}]}\n')

        session._executor.run_streaming = mock_streaming

        events = [event async for event in session.generate_stream("test")]

        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_stream_session_id_from_system_event(self):
        provider = ClaudeProvider()
        session = AgentSession(provider)

        async def mock_streaming(spec):
            yield ("stdout", '{"type":"system","session_id":"sys-sid"}\n')
            yield ("stdout", '{"type":"result","result":"ok","usage":{}}\n')

        session._executor.run_streaming = mock_streaming

        async for _ in session.generate_stream("test"):
            pass

        assert session.session_id == "sys-sid"

    @pytest.mark.asyncio
    async def test_stream_uses_override_cwd_and_timeout(self):
        provider = ClaudeProvider()
        session = AgentSession(provider, cwd="/default", timeout=100)

        called_spec = None

        async def mock_streaming(spec):
            nonlocal called_spec
            called_spec = spec
            yield ("stdout", '{"type":"result","result":"ok","usage":{}}\n')

        session._executor.run_streaming = mock_streaming

        async for _ in session.generate_stream("test", cwd="/custom", timeout=42):
            pass

        assert called_spec.cwd == "/custom"
        assert called_spec.timeout == 42.0


class TestSessionAsyncContextManager:
    @pytest.mark.asyncio
    async def test_enter_returns_self(self):
        provider = ClaudeProvider()
        session = AgentSession(provider)
        async with session as s:
            assert s is session

    @pytest.mark.asyncio
    async def test_exit_is_noop(self):
        provider = ClaudeProvider()
        session = AgentSession(provider)
        async with session:
            pass

    def test_session_usage_property(self):
        provider = ClaudeProvider()
        session = AgentSession(provider)
        usage = session.usage
        assert usage.total_input_tokens == 0
        assert usage.turn_count == 0
