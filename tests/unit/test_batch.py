"""Tests for agentpipe.batch — run_batch / iter_batch."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agentpipe._agent import Agent
from agentpipe._session import AgentSession
from agentpipe._types import GenerationResult, UsageEvent
from agentpipe.batch import BatchItem, _normalize_prompts, iter_batch, run_batch


class TestNormalizePrompts:
    def test_strings_get_index_ids(self):
        assert _normalize_prompts(["a", "b"]) == [("0", "a"), ("1", "b")]

    def test_tuples_pass_through(self):
        assert _normalize_prompts([("x", "a"), (7, "b")]) == [("x", "a"), ("7", "b")]

    def test_dicts_use_prompt_and_id_keys(self):
        pairs = _normalize_prompts([{"id": "q1", "prompt": "a"}, {"prompt": "b"}])
        assert pairs == [("q1", "a"), ("1", "b")]

    def test_dict_without_prompt_raises(self):
        with pytest.raises(ValueError, match="no 'prompt' key"):
            _normalize_prompts([{"id": "q1"}])


class TestBatchItem:
    def test_ok_and_to_dict(self):
        item = BatchItem(index=0, id="0", prompt="p", text="t")
        assert item.ok
        data = item.to_dict()
        assert data["ok"] is True
        assert data["text"] == "t"

    def test_failed_item(self):
        item = BatchItem(index=0, id="0", prompt="p", error="boom")
        assert not item.ok
        assert item.to_dict()["ok"] is False


class TestRunBatch:
    @pytest.mark.asyncio
    async def test_results_in_input_order(self):
        agent = Agent("claude", model="mock")

        async def mock_generate(self_session, prompt, **kwargs):
            return GenerationResult(text=f"out:{prompt}", returncode=0)

        with patch.object(AgentSession, "generate_full", mock_generate):
            items = await run_batch(["a", "b", "c"], agent=agent, max_concurrency=2)

        assert [i.text for i in items] == ["out:a", "out:b", "out:c"]
        assert [i.index for i in items] == [0, 1, 2]
        assert all(i.ok for i in items)
        assert items[0].provider == "claude"

    @pytest.mark.asyncio
    async def test_failure_is_captured_not_raised(self):
        agent = Agent("claude", model="mock")

        async def mock_generate(self_session, prompt, **kwargs):
            if prompt == "bad":
                raise RuntimeError("kaboom")
            return GenerationResult(text="fine", returncode=0)

        with patch.object(AgentSession, "generate_full", mock_generate):
            items = await run_batch(["ok", "bad"], agent=agent)

        assert items[0].ok
        assert not items[1].ok
        assert "kaboom" in items[1].error

    @pytest.mark.asyncio
    async def test_retries_recover_flaky_items(self):
        agent = Agent("claude", model="mock")
        calls = {"n": 0}

        async def mock_generate(self_session, prompt, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient")
            return GenerationResult(text="recovered", returncode=0)

        with patch.object(AgentSession, "generate_full", mock_generate):
            items = await run_batch(["a"], agent=agent, max_retries=1)

        assert items[0].ok
        assert items[0].text == "recovered"

    @pytest.mark.asyncio
    async def test_skip_ids(self):
        agent = Agent("claude", model="mock")

        async def mock_generate(self_session, prompt, **kwargs):
            return GenerationResult(text="x", returncode=0)

        with patch.object(AgentSession, "generate_full", mock_generate):
            items = await run_batch([("a", "p1"), ("b", "p2")], agent=agent, skip_ids={"a"})

        assert [i.id for i in items] == ["b"]

    @pytest.mark.asyncio
    async def test_usage_is_recorded(self):
        agent = Agent("claude", model="mock")
        usage = UsageEvent(input_tokens=10, output_tokens=20, cost_usd=0.01)

        async def mock_generate(self_session, prompt, **kwargs):
            return GenerationResult(text="x", usage=usage, returncode=0)

        with patch.object(AgentSession, "generate_full", mock_generate):
            items = await run_batch(["a"], agent=agent)

        assert items[0].cost_usd == 0.01
        assert items[0].input_tokens == 10
        assert items[0].output_tokens == 20

    @pytest.mark.asyncio
    async def test_on_result_callback_fires(self):
        agent = Agent("claude", model="mock")
        seen: list[str] = []

        async def mock_generate(self_session, prompt, **kwargs):
            return GenerationResult(text="x", returncode=0)

        with patch.object(AgentSession, "generate_full", mock_generate):
            await run_batch(["a", "b"], agent=agent, on_result=lambda i: seen.append(i.id))

        assert sorted(seen) == ["0", "1"]


class TestIterBatch:
    @pytest.mark.asyncio
    async def test_yields_every_item(self):
        agent = Agent("claude", model="mock")

        async def mock_generate(self_session, prompt, **kwargs):
            return GenerationResult(text=f"out:{prompt}", returncode=0)

        ids = set()
        with patch.object(AgentSession, "generate_full", mock_generate):
            async for item in iter_batch(["a", "b", "c"], agent=agent):
                ids.add(item.id)

        assert ids == {"0", "1", "2"}

    @pytest.mark.asyncio
    async def test_cascade_mode_used_without_agent(self):
        from agentpipe.cascade import CascadeResult

        async def mock_cascade(prompt, **kwargs):
            return CascadeResult(text=f"casc:{prompt}", successful_model="m", successful_provider="p")

        with patch("agentpipe.batch.cascade", mock_cascade):
            items = await run_batch(["a"])

        assert items[0].text == "casc:a"
        assert items[0].model == "m"
        assert items[0].provider == "p"
