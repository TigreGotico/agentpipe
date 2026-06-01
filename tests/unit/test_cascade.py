import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from agentpipe._executor import AgentProcessError
from agentpipe._session import AgentSession
from agentpipe._types import GenerationResult, SessionUsage
from agentpipe.cascade import (
    CASCADE_PROFILES,
    MODEL_TIER_MAP,
    ErrorType,
    ModelTier,
    cascade,
    cascade_coding,
    cascade_fast_free,
    cascade_free_only,
    tier_summary,
)


def _make_result(text: str, cost_usd: float = 0.0) -> GenerationResult:
    return GenerationResult(
        text=text,
        session_id="test-session",
        returncode=0,
        usage=SessionUsage(cost_usd=cost_usd, input_tokens=10, output_tokens=20) if cost_usd else None,
    )


def _make_rate_limit_error(provider: str = "gemini", resets_in: int = 60) -> AgentProcessError:
    return AgentProcessError(
        returncode=1,
        stderr=f"You have exhausted your capacity on this model. Your quota will reset after {resets_in}s",
        argv=["gemini"],
    )


def _make_process_error() -> AgentProcessError:
    return AgentProcessError(returncode=1, stderr="fatal error", argv=["opencode"])


class TestCascadeProfiles:
    def test_default_profile_exists(self):
        assert "default" in CASCADE_PROFILES
        assert len(CASCADE_PROFILES["default"]) > 0

    def test_all_profiles_have_models(self):
        for name, models in CASCADE_PROFILES.items():
            assert len(models) > 0, f"Profile {name!r} has no models"

    def test_coding_profile(self):
        models = CASCADE_PROFILES["coding"]
        assert any("big-pickle" in m for m in models)

    def test_free_only_profile(self):
        models = CASCADE_PROFILES["free-only"]
        for m in models:
            assert MODEL_TIER_MAP.get(m) == ModelTier.FREE, f"{m} is not free-tier"


class TestCascadeSuccess:
    @pytest.mark.asyncio
    async def test_cascade_succeeds_first_model(self):
        with patch.object(AgentSession, "generate_full", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = _make_result("hello from big-pickle")

            result = await cascade("test prompt", models=["opencode/big-pickle"])
            assert result.text == "hello from big-pickle"
            assert result.successful_model == "opencode/big-pickle"
            assert len(result.attempts) == 1
            assert result.attempts[0].success is True


class TestCascadeFallback:
    @pytest.mark.asyncio
    async def test_falls_back_on_process_error(self):
        call_count = 0

        async def mock_generate(self_session, prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _make_process_error()
            return _make_result("success on second")

        with patch.object(AgentSession, "generate_full", mock_generate):
            result = await cascade(
                "test",
                models=["opencode/big-pickle", "gemini-2.5-flash"],
                retry_delay_seconds=0,
            )
            assert result.text == "success on second"
            assert result.successful_model == "gemini-2.5-flash"
            assert len(result.attempts) == 2
            assert result.attempts[0].success is False
            assert result.attempts[0].error_type == ErrorType.PROCESS_ERROR
            assert result.attempts[1].success is True

    @pytest.mark.asyncio
    async def test_falls_back_on_rate_limit(self):
        call_count = 0

        async def mock_generate(self_session, prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _make_rate_limit_error()
            return _make_result("success after rate limit")

        with patch.object(AgentSession, "generate_full", mock_generate):
            result = await cascade(
                "test",
                models=["gemini-2.5-flash", "opencode/big-pickle"],
                retry_delay_seconds=0,
                rate_limit_backoff_seconds=0,
            )
            assert result.text == "success after rate limit"
            assert result.attempts[0].error_type == ErrorType.RATE_LIMIT
            assert result.attempts[0].rate_limit_resets_in == 60

    @pytest.mark.asyncio
    async def test_falls_back_on_timeout(self):
        call_count = 0

        async def mock_generate(self_session, prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError
            return _make_result("success after timeout")

        with patch.object(AgentSession, "generate_full", mock_generate):
            result = await cascade(
                "test",
                models=["opencode/big-pickle", "gemini-2.5-flash"],
                retry_delay_seconds=0,
            )
            assert result.text == "success after timeout"
            assert result.attempts[0].error_type == ErrorType.TIMEOUT


class TestCascadeLimits:
    @pytest.mark.asyncio
    async def test_max_attempts_stops_early(self):
        with patch.object(
            AgentSession,
            "generate_full",
            new_callable=AsyncMock,
            side_effect=_make_process_error(),
        ):
            with pytest.raises(RuntimeError, match="All 3 models failed"):
                await cascade(
                    "test",
                    models=["opencode/big-pickle", "gemini-2.5-flash", "opencode/deepseek-v4-flash-free"],
                    max_attempts=3,
                    retry_delay_seconds=0,
                )

    @pytest.mark.asyncio
    async def test_max_tier_filters_models(self):
        async def mock_generate(self_session, prompt, **kwargs):
            return _make_result("ok")

        with patch.object(AgentSession, "generate_full", mock_generate):
            result = await cascade(
                "test",
                models=["opencode/big-pickle", "opencode/kimi-k2.5", "opencode/qwen3.6-plus"],
                max_tier=ModelTier.CHEAP,
                retry_delay_seconds=0,
            )
            assert result.successful_model == "opencode/big-pickle"
            assert result.attempt_count <= 3


class TestCascadeOnAttemptCallback:
    @pytest.mark.asyncio
    async def test_callback_called(self):
        attempts_log = []

        async def mock_generate(self_session, prompt, **kwargs):
            return _make_result("done")

        with patch.object(AgentSession, "generate_full", mock_generate):
            await cascade(
                "test",
                models=["opencode/big-pickle"],
                on_attempt=lambda a: attempts_log.append(a.model),
                retry_delay_seconds=0,
            )
        assert attempts_log == ["opencode/big-pickle"]


class TestCascadeAllFail:
    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_all_fail(self):
        with patch.object(
            AgentSession,
            "generate_full",
            new_callable=AsyncMock,
            side_effect=_make_process_error(),
        ):
            with pytest.raises(RuntimeError, match="All 2 models failed"):
                await cascade(
                    "test",
                    models=["opencode/big-pickle", "gemini-2.5-flash"],
                    retry_delay_seconds=0,
                )


class TestConvenienceFunctions:
    @pytest.mark.asyncio
    async def test_cascade_fast_free(self):
        async def mock_generate(self_session, prompt, **kwargs):
            return _make_result("fast and free")

        with patch.object(AgentSession, "generate_full", mock_generate):
            result = await cascade_fast_free("test prompt")
            assert result.text == "fast and free"

    @pytest.mark.asyncio
    async def test_cascade_free_only(self):
        async def mock_generate(self_session, prompt, **kwargs):
            return _make_result("free only")

        with patch.object(AgentSession, "generate_full", mock_generate):
            result = await cascade_free_only("test prompt")
            assert result.text == "free only"

    @pytest.mark.asyncio
    async def test_cascade_coding(self):
        async def mock_generate(self_session, prompt, **kwargs):
            return _make_result("coding result")

        with patch.object(AgentSession, "generate_full", mock_generate):
            result = await cascade_coding("test prompt")
            assert result.text == "coding result"


class TestTierSummary:
    def test_returns_all_tiers(self):
        summary = tier_summary()
        assert set(summary.keys()) == {ModelTier.FREE, ModelTier.CHEAP, ModelTier.MID, ModelTier.PREMIUM}

    def test_free_tier_has_models(self):
        summary = tier_summary()
        assert len(summary[ModelTier.FREE]) > 0


class TestResolveProvider:
    def test_free_model_maps_to_opencode_free(self):
        from agentpipe.cascade import _resolve_provider

        assert _resolve_provider("opencode/big-pickle") == "opencode-free"
        assert _resolve_provider("opencode/deepseek-v4-flash-free") == "opencode-free"
        assert _resolve_provider("opencode/gemini-3-flash") == "opencode-free"

    def test_zen_model_maps_to_opencode_zen(self):
        from agentpipe.cascade import _resolve_provider

        assert _resolve_provider("opencode/kimi-k2.5") == "opencode-zen"
        assert _resolve_provider("opencode/kimi-k2.6") == "opencode-zen"
        assert _resolve_provider("opencode/glm-5.1") == "opencode-zen"

    def test_go_model_maps_to_opencode_go(self):
        from agentpipe.cascade import _resolve_provider

        assert _resolve_provider("opencode-go/deepseek-v4-flash") == "opencode-go"
        assert _resolve_provider("opencode-go/glm-5.1") == "opencode-go"

    def test_gemini_models_map_to_gemini(self):
        from agentpipe.cascade import _resolve_provider

        assert _resolve_provider("gemini-2.5-flash") == "gemini"
        assert _resolve_provider("gemini-2.5-pro") == "gemini"

    def test_unknown_model_raises(self):
        from agentpipe.cascade import _resolve_provider

        with pytest.raises(ValueError, match="Cannot determine provider"):
            _resolve_provider("unknown-model")


class TestProviderClasses:
    def test_opencode_free_provider(self):
        from agentpipe.providers.opencode import OpencodeFreeProvider

        p = OpencodeFreeProvider()
        assert p.model == "opencode/big-pickle"
        assert p.plan == "free"
        assert p.binary_name == "opencode"

    def test_opencode_zen_provider(self):
        from agentpipe.providers.opencode import OpencodeZenProvider

        p = OpencodeZenProvider()
        assert p.model == "opencode/gemini-3-flash"
        assert p.plan == "zen"
        assert p.binary_name == "opencode"

    def test_opencode_go_provider(self):
        from agentpipe.providers.opencode import OpencodeGoProvider

        p = OpencodeGoProvider()
        assert p.model == "opencode-go/deepseek-v4-flash"
        assert p.plan == "go"
        assert p.binary_name == "opencode"

    def test_opencode_provider_backward_compat(self):
        from agentpipe.providers.opencode import OpencodeProvider

        p = OpencodeProvider()
        assert p.model == "opencode/gemini-3-flash"
        assert p.plan == "zen"

    def test_claude_sonnet_provider(self):
        from agentpipe.providers.claude import ClaudeSonnetProvider

        p = ClaudeSonnetProvider()
        assert p.model == "sonnet"

    def test_claude_haiku_provider(self):
        from agentpipe.providers.claude import ClaudeHaikuProvider

        p = ClaudeHaikuProvider()
        assert p.model == "haiku"

    def test_claude_opus_provider(self):
        from agentpipe.providers.claude import ClaudeOpusProvider

        p = ClaudeOpusProvider()
        assert p.model == "opus"

    def test_gemini_flash_provider(self):
        from agentpipe.providers.gemini import GeminiFlashProvider

        p = GeminiFlashProvider()
        assert p.model == "gemini-2.5-flash"

    def test_gemini_pro_provider(self):
        from agentpipe.providers.gemini import GeminiProProvider

        p = GeminiProProvider()
        assert p.model == "gemini-2.5-pro"
