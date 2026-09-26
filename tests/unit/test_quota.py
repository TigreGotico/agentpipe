"""Tests for agentpipe._quota — quota checking and rate-limit parsing."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from agentpipe._executor import AgentProcessError, AsyncSubprocessExecutor
from agentpipe._quota import check_quota, parse_rate_limit_error


class TestCheckQuota:
    @pytest.mark.asyncio
    async def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            await check_quota("nonexistent")

    @pytest.mark.asyncio
    async def test_defaults_to_claude(self):
        executor = AsyncSubprocessExecutor()
        executor.run = AsyncMock(
            return_value=(json.dumps({"loggedIn": True, "subscriptionType": "pro", "email": "a@b.c"}), "")
        )
        result = await check_quota(executor=executor)
        assert result.provider == "claude"
        assert result.authenticated is True

    @pytest.mark.asyncio
    async def test_claude_quota_success(self):
        executor = AsyncSubprocessExecutor()
        executor.run = AsyncMock(
            return_value=(json.dumps({"loggedIn": True, "subscriptionType": "max", "email": "u@x.y"}), "")
        )
        result = await check_quota("claude", executor=executor)
        assert result.authenticated is True
        assert result.subscription_type == "max"
        assert result.email == "u@x.y"
        assert result.plan_limits.get("tier") == "max"

    @pytest.mark.asyncio
    async def test_claude_quota_failure(self):
        executor = AsyncSubprocessExecutor()
        executor.run = AsyncMock(side_effect=AgentProcessError(1, "fail", ["claude"]))
        result = await check_quota("claude", executor=executor)
        assert result.authenticated is False
        assert result.raw_error is not None

    @pytest.mark.asyncio
    async def test_gemini_quota_authenticated(self):
        call_count = 0

        async def mock_run(spec):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("gemini-cli 1.0", "")
            return ("test output", "")

        executor = AsyncSubprocessExecutor()
        executor.run = AsyncMock(side_effect=mock_run)
        result = await check_quota("gemini", executor=executor)
        assert result.provider == "gemini"
        assert result.authenticated is True

    @pytest.mark.asyncio
    async def test_gemini_quota_rate_limited_stderr(self):
        call_count = 0

        async def mock_run(spec):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("version", "")
            return ("", "Your quota will reset after 120s")

        executor = AsyncSubprocessExecutor()
        executor.run = AsyncMock(side_effect=mock_run)
        result = await check_quota("gemini", executor=executor)
        assert result.rate_limited is True
        assert result.rate_limit_resets_in_seconds == 120

    @pytest.mark.asyncio
    async def test_gemini_quota_rate_limited_exception(self):
        call_count = 0

        async def mock_run(spec):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("version", "")
            raise AgentProcessError(
                1,
                "You have exhausted your capacity on this model. Your quota will reset after 30s",
                ["gemini"],
            )

        executor = AsyncSubprocessExecutor()
        executor.run = AsyncMock(side_effect=mock_run)
        result = await check_quota("gemini", executor=executor)
        assert result.rate_limited is True
        assert result.rate_limit_resets_in_seconds == 30

    @pytest.mark.asyncio
    async def test_opencode_quota(self):
        call_count = 0

        async def mock_run(spec):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("provider1\nprovider2\n", "")
            if call_count == 2:
                return ("model-a\nmodel-b\n", "")
            return ("usage data", "")

        executor = AsyncSubprocessExecutor()
        executor.run = AsyncMock(side_effect=mock_run)
        result = await check_quota("opencode-free", executor=executor)
        assert result.provider == "opencode"
        assert result.authenticated is True
        assert "model-a" in result.available_models

    @pytest.mark.asyncio
    async def test_unsupported_provider_returns_basic_status(self):
        executor = AsyncSubprocessExecutor()
        result = await check_quota("aider", executor=executor)
        assert result.provider == "aider"


class TestParseRateLimitError:
    def test_gemini_rate_limit_with_seconds(self):
        err = AgentProcessError(1, "Your quota will reset after 60s", ["gemini"])
        info = parse_rate_limit_error("gemini", err)
        assert info["rate_limited"] is True
        assert info["resets_in_seconds"] == 60

    def test_gemini_rate_limit_generic(self):
        err = AgentProcessError(
            1,
            "You have exhausted your capacity on this model. Your quota will reset after 45s",
            ["gemini"],
        )
        info = parse_rate_limit_error("gemini", err)
        assert info["rate_limited"] is True
        assert info["resets_in_seconds"] == 45

    def test_opencode_rate_limit(self):
        err = AgentProcessError(1, "rate limit exceeded", ["opencode"])
        info = parse_rate_limit_error("opencode", err)
        assert info["rate_limited"] is True

    def test_opencode_prefixed_rate_limit(self):
        err = AgentProcessError(1, "too many requests", ["opencode-free"])
        info = parse_rate_limit_error("opencode-free", err)
        assert info["rate_limited"] is True

    def test_claude_rate_limit(self):
        err = AgentProcessError(1, "rate limit reached", ["claude"])
        info = parse_rate_limit_error("claude", err)
        assert info["rate_limited"] is True

    def test_claude_overloaded(self):
        err = AgentProcessError(1, "server overloaded please retry", ["claude"])
        info = parse_rate_limit_error("claude", err)
        assert info["rate_limited"] is True

    def test_no_rate_limit(self):
        err = AgentProcessError(1, "syntax error", ["claude"])
        info = parse_rate_limit_error("claude", err)
        assert info["rate_limited"] is False

    def test_unknown_provider_no_match(self):
        err = AgentProcessError(1, "rate limit", ["vibe"])
        info = parse_rate_limit_error("vibe", err)
        assert info["rate_limited"] is False

    def test_empty_stderr(self):
        err = AgentProcessError(1, "", ["gemini"])
        info = parse_rate_limit_error("gemini", err)
        assert info["rate_limited"] is False
