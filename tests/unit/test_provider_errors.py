"""A provider failure must not come back looking like an answer.

aider exits 0 after printing litellm's complaint, so nothing downstream could
tell an error from a reply and the error text was served as the assistant's
message. The output below is what aider 0.86.2 actually printed when it was
handed a model string it could not resolve.
"""

from __future__ import annotations

import pytest

from agentpipe import ProviderOutputError
from agentpipe._session import AgentSession
from agentpipe.providers.aider import AiderProvider
from agentpipe.providers.kilo import KiloProvider

AIDER_UNRESOLVABLE_MODEL_OUTPUT = """Aider v0.86.2
Model: aider/openrouter/google/gemma-4-26b-a4b-it:free with whole edit format
Git repo: .git with 0 files
Repo-map: using 1024 tokens, auto refresh

litellm.BadRequestError: LLM Provider NOT provided. Pass in the LLM provider you
are trying to call. You passed
model=aider/openrouter/google/gemma-4-26b-a4b-it:free
 Pass model as E.g. For 'Huggingface' inference endpoints pass in
`completion(model='huggingface/starcoder',..)` Learn more:
https://docs.litellm.ai/docs/providers
"""

AIDER_ANSWER_OUTPUT = """Aider v0.86.2
Model: openrouter/google/gemma-3-27b-it:free with whole edit format
Git repo: .git with 0 files

Hi there!
Tokens: 12 sent, 3 received
"""


class TestAiderErrorDetection:
    def test_a_litellm_failure_is_recognised(self):
        lines = AIDER_UNRESOLVABLE_MODEL_OUTPUT.splitlines(keepends=True)
        error = AiderProvider().detect_error(lines)
        assert error is not None
        assert "litellm.BadRequestError" in error
        assert "LLM Provider NOT provided" in error

    def test_an_ordinary_answer_is_not_an_error(self):
        lines = AIDER_ANSWER_OUTPUT.splitlines(keepends=True)
        assert AiderProvider().detect_error(lines) is None

    def test_other_providers_report_failures_by_exit_code(self):
        assert KiloProvider().detect_error(["anything\n"]) is None


AIDER_RATE_LIMITED_THEN_ANSWERED = """Aider v0.86.2
Model: openrouter/google/gemma-3-27b-it:free with whole edit format

litellm.RateLimitError: RateLimitError: OpenrouterException - rate limit exceeded
The API provider has rate limited you. Try again later or check your quotas.
Retrying in 0.2 seconds...

The capital of France is Paris.
Tokens: 12 sent, 4 received
"""


class TestARetriedErrorIsNotAFailure:
    """aider prints litellm's text for errors it recovers from too, so the
    text alone cannot mean the request failed. Rate limits are the common
    case and usually succeed on the next attempt."""

    def test_an_error_aider_retried_past_is_not_reported(self):
        lines = AIDER_RATE_LIMITED_THEN_ANSWERED.splitlines(keepends=True)
        assert AiderProvider().detect_error(lines) is None

    def test_the_answer_after_a_retry_still_comes_through(self):
        lines = AIDER_RATE_LIMITED_THEN_ANSWERED.splitlines(keepends=True)
        assert "Paris" in AiderProvider().extract_text(lines)

    def test_the_error_that_ends_the_run_is_still_reported(self):
        lines = AIDER_UNRESOLVABLE_MODEL_OUTPUT.splitlines(keepends=True)
        error = AiderProvider().detect_error(lines)
        assert error is not None and "litellm.BadRequestError" in error


class TestTheSessionRefusesToReturnAnErrorAsText:
    @pytest.mark.asyncio
    async def test_generate_full_raises_instead_of_answering(self):
        session = AgentSession(AiderProvider())

        async def run(spec):
            return AIDER_UNRESOLVABLE_MODEL_OUTPUT, ""

        session._executor.run = run

        with pytest.raises(ProviderOutputError) as excinfo:
            await session.generate_full("say hi")

        assert "litellm.BadRequestError" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_a_real_answer_still_comes_back(self):
        session = AgentSession(AiderProvider())

        async def run(spec):
            return AIDER_ANSWER_OUTPUT, ""

        session._executor.run = run

        result = await session.generate_full("say hi")
        assert "Hi there!" in result.text

    @pytest.mark.asyncio
    async def test_the_stream_raises_too(self):
        session = AgentSession(AiderProvider())

        async def run_streaming(spec):
            for line in AIDER_UNRESOLVABLE_MODEL_OUTPUT.splitlines(keepends=True):
                yield ("stdout", line)

        session._executor.run_streaming = run_streaming

        with pytest.raises(ProviderOutputError):
            async for _ in session.generate_stream("say hi"):
                pass


class TestTheOpenAIEndpointDoesNotReturn200OnAFailure:
    def test_a_provider_failure_is_an_error_response(self):
        fastapi = pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        from agentpipe import server

        class _FakeProviderInstance:
            # The route looks the CLI up in PATH first, so name one that is
            # always there.
            binary_name = "sh"

        class _FailingAgent:
            _provider_instance = _FakeProviderInstance()
            provider = "aider"
            model = "openrouter/google/x:free"
            timeout = 300
            cwd = "/tmp"
            continue_last = False

            async def generate_full(self, prompt):
                raise ProviderOutputError("litellm.BadRequestError: nope")

        server._agents.clear()
        original = server._build_openai_agent
        server._build_openai_agent = lambda provider, model: _FailingAgent()
        try:
            client = TestClient(server.app, raise_server_exceptions=False)
            response = client.post("/v1/chat/completions", json={
                "model": "aider/openrouter/google/x:free",
                "messages": [{"role": "user", "content": "say hi"}]})
        finally:
            server._build_openai_agent = original
            server._agents.clear()

        assert response.status_code >= 400, response.text
        assert "choices" not in response.json()
        assert fastapi is not None


    def test_a_streaming_failure_does_not_finish_with_stop(self):
        """A stream cannot change its status code, so finish_reason is the
        only place left to say the answer failed. It used to say "stop",
        and the openai SDK reads that as a short but complete reply."""
        pytest.importorskip("fastapi")
        pytest.importorskip("sse_starlette")
        from fastapi.testclient import TestClient

        from agentpipe import server

        class _FakeProviderInstance:
            binary_name = "sh"

        class _FailingSession:
            session_id = None

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def generate_stream(self, prompt):
                raise ProviderOutputError("litellm.BadRequestError: nope")
                yield  # pragma: no cover - makes this an async generator

        class _FailingAgent:
            _provider_instance = _FakeProviderInstance()
            provider = "aider"
            model = "openrouter/google/x:free"
            timeout = 300
            cwd = "/tmp"
            continue_last = False

            def session(self):
                return _FailingSession()

        server._agents.clear()
        original = server._build_openai_agent
        server._build_openai_agent = lambda provider, model: _FailingAgent()
        try:
            client = TestClient(server.app, raise_server_exceptions=False)
            response = client.post("/v1/chat/completions", json={
                "model": "aider/openrouter/google/x:free",
                "stream": True,
                "messages": [{"role": "user", "content": "say hi"}]})
            body = response.text
        finally:
            server._build_openai_agent = original
            server._agents.clear()

        assert '"finish_reason": "stop"' not in body, body
        assert "litellm.BadRequestError" in body, body


class TestModelRouting:
    """A prefix that only picks the provider must not reach the CLI."""

    def test_the_aider_prefix_is_stripped(self):
        pytest.importorskip("fastapi")
        from agentpipe.server import _route_model

        assert _route_model("aider/openrouter/google/gemma-3-27b-it:free") == (
            "aider", "openrouter/google/gemma-3-27b-it:free")

    def test_a_namespace_prefix_is_part_of_the_model(self):
        pytest.importorskip("fastapi")
        from agentpipe.server import _route_model

        # kilo's own models really are called "kilo/...", and aider's really
        # are called "openrouter/...".
        assert _route_model("kilo/kilo-auto/free") == ("kilo", "kilo/kilo-auto/free")
        assert _route_model("openrouter/google/gemma-3-27b-it:free") == (
            "aider", "openrouter/google/gemma-3-27b-it:free")
        assert _route_model("xiaomi/mimo-v2.5-pro") == ("mimo", "xiaomi/mimo-v2.5-pro")
        assert _route_model("opencode-go/deepseek-v4-flash") == (
            "opencode-go", "opencode-go/deepseek-v4-flash")

    def test_routing_only_prefixes_come_off_for_every_provider(self):
        pytest.importorskip("fastapi")
        from agentpipe.server import _route_model

        assert _route_model("claude/sonnet") == ("claude", "sonnet")
        assert _route_model("gemini/gemini-2.5-pro") == ("gemini", "gemini-2.5-pro")
        assert _route_model("vibe/mistral-large-latest") == ("vibe", "mistral-large-latest")

    def test_a_bare_alias_names_no_model(self):
        pytest.importorskip("fastapi")
        from agentpipe.server import _route_model

        assert _route_model("aider") == ("aider", None)
        assert _route_model("opencode-free") == ("opencode-free", None)

    def test_the_stripped_model_is_what_the_cli_receives(self):
        pytest.importorskip("fastapi")
        from agentpipe import Agent
        from agentpipe.server import _route_model

        provider, model = _route_model("aider/openrouter/google/gemma-3-27b-it:free")
        cmd = Agent(provider, model=model)._provider_instance.build_command("hi")
        assert "openrouter/google/gemma-3-27b-it:free" in cmd
        assert "aider/openrouter/google/gemma-3-27b-it:free" not in cmd
