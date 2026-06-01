from unittest.mock import patch

import pytest

from agentpipe._agent import Agent
from agentpipe._pipeline import delegate, fan_out, map_concurrent, retry_until
from agentpipe._session import AgentSession
from agentpipe._types import GenerationResult


class TestFanOut:
    @pytest.mark.asyncio
    async def test_fan_out_basic(self):
        agent = Agent("claude", model="mock")

        with patch.object(
            AgentSession,
            "generate_full",
            side_effect=[
                GenerationResult(text="result-0", session_id="s1", returncode=0),
                GenerationResult(text="result-1", session_id="s2", returncode=0),
                GenerationResult(text="result-2", session_id="s3", returncode=0),
            ],
        ):
            results = await fan_out(agent, ["a", "b", "c"])
            assert results == ["result-0", "result-1", "result-2"]


class TestDelegate:
    @pytest.mark.asyncio
    async def test_delegate_drafts_then_reviews(self):
        draft_agent = Agent("gemini", model="flash")
        review_agent = Agent("claude", model="sonnet")

        call_count = 0

        async def mock_generate(self_session, prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return GenerationResult(text="draft output", session_id="d1", returncode=0)
            assert "draft output" in prompt
            return GenerationResult(text="reviewed output", session_id="r1", returncode=0)

        with patch.object(AgentSession, "generate_full", mock_generate):
            result = await delegate(draft_agent, review_agent, "Write tests", "Review these")
            assert result == "reviewed output"


class TestRetryUntil:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        agent = Agent("claude")

        async def mock_generate(self_session, prompt, **kwargs):
            return GenerationResult(text="passed validation", session_id="s1", returncode=0)

        with patch.object(AgentSession, "generate_full", mock_generate):
            result = await retry_until(agent, "do thing", validator=lambda r: "passed" in r)
            assert result == "passed validation"

    @pytest.mark.asyncio
    async def test_retries_until_valid(self):
        agent = Agent("claude")
        call_count = 0

        async def mock_generate(self_session, prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            texts = ["fail 1", "fail 2", "passed"]
            return GenerationResult(
                text=texts[min(call_count - 1, 2)],
                session_id=f"s{call_count}",
                returncode=0,
            )

        with patch.object(AgentSession, "generate_full", mock_generate):
            result = await retry_until(agent, "do thing", validator=lambda r: "passed" in r, max_attempts=3)
            assert "passed" in result


class TestMapConcurrent:
    @pytest.mark.asyncio
    async def test_sends_to_multiple_agents(self):
        agents = [Agent("claude"), Agent("gemini")]

        call_idx = 0

        async def mock_generate(self_session, prompt, **kwargs):
            nonlocal call_idx
            call_idx += 1
            return GenerationResult(
                text=f"response-{call_idx}",
                session_id=f"s{call_idx}",
                returncode=0,
            )

        with patch.object(AgentSession, "generate_full", mock_generate):
            results = await map_concurrent(agents, "explain this")
            assert len(results) == 2
