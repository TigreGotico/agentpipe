"""Stateless mode and the safety of the anonymous OpenAI surface.

These assert against a real ``Agent`` and the command line its provider builds,
because that is what the CLI actually receives. Asserting on a mocked Agent
proves nothing: a mock accepts any constructor argument and reports whatever
the test set by hand.

The request-isolation tests go through the real app with a stand-in agent that
answers with its own history when told to continue, so a leak shows up as the
wrong answer in the response body rather than as a flag someone asserted on.
"""
import importlib
import json
import sys

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from agentpipe import Agent, GenerationResult
from agentpipe._types import ApprovalMode, ThinkingEvent


class _FakeProviderInstance:
    # The route looks the CLI up in PATH before it runs anything, so this
    # names a binary that is always there.
    binary_name = "sh"


class _RecordingAgent:
    """An Agent stand-in that behaves like a resumable provider session.

    It answers with its own history when the server asks it to continue, and
    with the current prompt alone when it does not. A leak is therefore
    visible in the response body instead of having to be inferred from a flag.
    """

    _provider_instance = _FakeProviderInstance()

    def __init__(self, provider, model):
        self.provider = provider
        self.model = model
        self.timeout = 300
        self.cwd = "/tmp"
        self.continue_last = False
        self.history = []

    async def generate_full(self, prompt):
        return GenerationResult(text=self._answer(prompt), events=(),
                                session_id="ses-1", usage=None, returncode=0)

    def session(self):
        return _RecordingSession(self)

    def _answer(self, prompt):
        """Answer with the whole conversation when told to continue it."""
        self.history.append(prompt)
        return "\n".join(self.history) if self.continue_last else prompt


class _RecordingSession:
    """What _RecordingAgent.session() hands the streaming route."""

    def __init__(self, agent):
        self._agent = agent
        self.session_id = "ses-1"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def generate_stream(self, prompt):
        yield ThinkingEvent(text=self._agent._answer(prompt))


def _stub_agents(monkeypatch, server):
    """Make the server build _RecordingAgents, and return the list of them."""
    built = []

    def build(provider, model):
        agent = _RecordingAgent(provider, model)
        built.append(agent)
        return agent

    monkeypatch.setattr(server, "_build_openai_agent", build)
    return built


def _stream_content(response):
    """Join the assistant text out of an SSE chat-completion stream."""
    parts = []
    for line in response.text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        delta = json.loads(payload)["choices"][0]["delta"]
        parts.append(delta.get("content") or "")
    return "".join(parts)


def _client(server):
    server._agents.clear()
    return TestClient(server.app)


def _load_server(monkeypatch, **env):
    """Import agentpipe.server with the given environment."""
    for key in ("AGENTPIPE_STATELESS", "AGENTPIPE_OPENAI_APPROVAL",
                "AGENTPIPE_MAX_CONCURRENCY", "AGENTPIPE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    sys.modules.pop("agentpipe.server", None)
    module = importlib.import_module("agentpipe.server")
    # Leave nothing behind for the next importer of this module.
    monkeypatch.undo
    return module


class TestContinueLastReachesTheProvider:
    """Agent folds this into its provider at construction."""

    def test_setting_it_after_construction_takes_effect(self):
        # The provider is built once in __post_init__ and reused for every
        # call, so a plain field assignment used to be discarded and the CLI
        # never saw --continue.
        agent = Agent("opencode", model="opencode/deepseek-v4-flash-free")
        assert "--continue" not in agent._provider_instance.build_command("hi")

        agent.continue_last = True

        assert agent._provider_instance._continue_last is True
        assert "--continue" in agent._provider_instance.build_command("hi")

    def test_clearing_it_also_takes_effect(self):
        agent = Agent("opencode", model="opencode/deepseek-v4-flash-free",
                      continue_last=True)
        agent.continue_last = False
        assert "--continue" not in agent._provider_instance.build_command("hi")


class TestOpenAISurfaceIsAChatEndpoint:
    """It returns text, so the CLI's file and shell tools are not wanted."""

    def test_agent_does_not_ask_to_skip_permissions(self, monkeypatch):
        server = _load_server(monkeypatch)
        agent = server._build_openai_agent(
            "opencode", "opencode/deepseek-v4-flash-free")
        cmd = agent._provider_instance.build_command("hi")
        assert "--dangerously-skip-permissions" not in cmd
        assert agent._provider_instance._approval_mode is ApprovalMode.DEFAULT

    def test_an_operator_can_opt_back_in(self, monkeypatch):
        server = _load_server(monkeypatch, AGENTPIPE_OPENAI_APPROVAL="bypass")
        agent = server._build_openai_agent(
            "opencode", "opencode/deepseek-v4-flash-free")
        assert "--dangerously-skip-permissions" in \
            agent._provider_instance.build_command("hi")

    def test_an_unreadable_setting_falls_back_to_the_safe_mode(self, monkeypatch):
        server = _load_server(monkeypatch, AGENTPIPE_OPENAI_APPROVAL="nonsense")
        agent = server._build_openai_agent(
            "opencode", "opencode/deepseek-v4-flash-free")
        assert "--dangerously-skip-permissions" not in \
            agent._provider_instance.build_command("hi")


class TestStatelessMode:

    def test_flag_parsing_tolerates_surrounding_space(self, monkeypatch):
        # A trailing space in a .env file must not silently leave a public
        # server sharing sessions between callers.
        assert _load_server(monkeypatch, AGENTPIPE_STATELESS=" 1 ")._STATELESS
        assert _load_server(monkeypatch, AGENTPIPE_STATELESS="true")._STATELESS
        assert _load_server(monkeypatch, AGENTPIPE_STATELESS="on")._STATELESS
        assert not _load_server(monkeypatch, AGENTPIPE_STATELESS="0")._STATELESS
        assert not _load_server(monkeypatch, AGENTPIPE_STATELESS="")._STATELESS

    def test_concurrency_is_bounded(self, monkeypatch):
        server = _load_server(monkeypatch, AGENTPIPE_STATELESS="1",
                              AGENTPIPE_MAX_CONCURRENCY="3")
        # Stateless drops the shared per-agent lock and the _MAX_AGENTS
        # ceiling; without a limit each request starts its own subprocess.
        assert server._MAX_CONCURRENT == 3
        assert server._stateless_slots._value == 3

    def test_native_endpoints_keep_their_sessions(self, monkeypatch):
        """Stateless governs the anonymous surface, not named agents."""
        server = _load_server(monkeypatch, AGENTPIPE_STATELESS="1")
        source = __import__("inspect").getsource(server.generate)
        assert "_STATELESS" not in source
        source = __import__("inspect").getsource(server.generate_stream)
        assert "_STATELESS" not in source

    def test_a_named_user_gets_no_session_either(self, monkeypatch):
        """Without the flag a "user" keeps an agent; with it, nobody does."""
        server = _load_server(monkeypatch, AGENTPIPE_STATELESS="1")
        client = _client(server)
        agents = _stub_agents(monkeypatch, server)

        for _ in range(2):
            client.post("/v1/chat/completions", json={
                "model": "kilo/kilo-auto/free", "user": "alice",
                "messages": [{"role": "user", "content": "hi"}]})

        assert len(agents) == 2
        assert server._agents == {}


class TestTheOpenAISurfaceIsIndependentPerRequest:
    """Two unrelated callers must not land in one conversation."""

    def test_a_second_request_cannot_see_the_first(self, monkeypatch):
        server = _load_server(monkeypatch)
        client = _client(server)
        agents = _stub_agents(monkeypatch, server)

        client.post("/v1/chat/completions", json={
            "model": "kilo/kilo-auto/free",
            "messages": [{"role": "user", "content":
                          "Remember this secret number: 42117."}]})
        second = client.post("/v1/chat/completions", json={
            "model": "kilo/kilo-auto/free",
            "messages": [{"role": "user", "content":
                          "What secret number did I just tell you?"}]})

        answer = second.json()["choices"][0]["message"]["content"]
        assert "42117" not in answer, answer
        # Each request was served by its own agent, and none was kept.
        assert len(agents) == 2
        assert agents[0] is not agents[1]
        assert server._agents == {}
        assert client.get("/agents").json() == []

    def test_a_named_user_still_continues_its_own_conversation(self, monkeypatch):
        server = _load_server(monkeypatch)
        client = _client(server)
        agents = _stub_agents(monkeypatch, server)

        client.post("/v1/chat/completions", json={
            "model": "kilo/kilo-auto/free", "user": "alice",
            "messages": [{"role": "user", "content":
                          "Remember this secret number: 42117."}]})
        second = client.post("/v1/chat/completions", json={
            "model": "kilo/kilo-auto/free", "user": "alice",
            "messages": [{"role": "user", "content":
                          "What secret number did I just tell you?"}]})

        assert "42117" in second.json()["choices"][0]["message"]["content"]
        assert len(agents) == 1
        assert list(server._agents) == ["alice"]

    def test_a_second_stream_cannot_see_the_first(self, monkeypatch):
        """The streaming route decides on its own whether to resume."""
        server = _load_server(monkeypatch)
        client = _client(server)
        agents = _stub_agents(monkeypatch, server)

        def ask(content):
            return client.post("/v1/chat/completions", json={
                "model": "kilo/kilo-auto/free", "stream": True,
                "messages": [{"role": "user", "content": content}]})

        ask("Remember this secret number: 42117.")
        second = ask("What secret number did I just tell you?")

        answer = _stream_content(second)
        assert "42117" not in answer, answer
        assert len(agents) == 2
        assert agents[0] is not agents[1]
        assert server._agents == {}

    def test_a_named_user_still_continues_its_own_stream(self, monkeypatch):
        server = _load_server(monkeypatch)
        client = _client(server)
        agents = _stub_agents(monkeypatch, server)

        def ask(content):
            return client.post("/v1/chat/completions", json={
                "model": "kilo/kilo-auto/free", "stream": True, "user": "alice",
                "messages": [{"role": "user", "content": content}]})

        ask("Remember this secret number: 42117.")
        second = ask("What secret number did I just tell you?")

        assert "42117" in _stream_content(second)
        assert len(agents) == 1
        assert list(server._agents) == ["alice"]

    def test_two_users_do_not_share_an_agent(self, monkeypatch):
        server = _load_server(monkeypatch)
        client = _client(server)
        agents = _stub_agents(monkeypatch, server)

        client.post("/v1/chat/completions", json={
            "model": "kilo/kilo-auto/free", "user": "alice",
            "messages": [{"role": "user", "content":
                          "Remember this secret number: 42117."}]})
        second = client.post("/v1/chat/completions", json={
            "model": "kilo/kilo-auto/free", "user": "bob",
            "messages": [{"role": "user", "content":
                          "What secret number did I just tell you?"}]})

        assert "42117" not in second.json()["choices"][0]["message"]["content"]
        assert len(agents) == 2
        assert sorted(server._agents) == ["alice", "bob"]


class TestEmptyApiKeyIsNoKey:
    """`AGENTPIPE_API_KEY: "${AGENTPIPE_API_KEY:-}"` in a compose file sets an
    empty string, and reading that as a real key locked out every caller."""

    async def test_empty_value_leaves_the_server_open(self, monkeypatch):
        server = _load_server(monkeypatch, AGENTPIPE_API_KEY="")
        assert server._API_KEY is None
        assert await server._require_auth(None) is None

    async def test_whitespace_only_value_leaves_the_server_open(self, monkeypatch):
        server = _load_server(monkeypatch, AGENTPIPE_API_KEY="   ")
        assert server._API_KEY is None
        assert await server._require_auth(None) is None

    async def test_a_real_key_is_still_required(self, monkeypatch):
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        server = _load_server(monkeypatch, AGENTPIPE_API_KEY="s3cret")
        assert server._API_KEY == "s3cret"
        with pytest.raises(HTTPException):
            await server._require_auth(None)
        good = HTTPAuthorizationCredentials(scheme="Bearer", credentials="s3cret")
        assert await server._require_auth(good) is None


class TestModelRoutingRefusesWhatItCannotPlace:
    """An unplaceable model used to fall through to kilo and fail inside the CLI."""

    def test_known_prefixes_reach_their_provider(self, monkeypatch):
        server = _load_server(monkeypatch)
        assert server._model_to_provider("opencode/big-pickle") == "opencode"
        assert server._model_to_provider("opencode-go/deepseek-v4-flash") == "opencode-go"
        assert server._model_to_provider("kilo/kilo-auto/free") == "kilo"
        assert server._model_to_provider("openrouter/google/gemma-4:free") == "aider"
        assert server._model_to_provider("xiaomi/mimo-v2.5-pro") == "mimo"

    def test_a_bare_provider_alias_is_accepted(self, monkeypatch):
        server = _load_server(monkeypatch)
        assert server._model_to_provider("opencode-free") == "opencode-free"
        assert server._model_to_provider("antigravity-flash-medium") == "antigravity-flash-medium"

    def test_an_unknown_model_is_refused_by_name(self, monkeypatch):
        from fastapi import HTTPException

        server = _load_server(monkeypatch)
        with pytest.raises(HTTPException) as exc:
            server._model_to_provider("gpt-4o")
        assert exc.value.status_code == 400
        assert "gpt-4o" in exc.value.detail

    def test_every_provider_alias_can_be_named(self, monkeypatch):
        server = _load_server(monkeypatch)
        from agentpipe._agent import _PROVIDER_MAP

        for alias in _PROVIDER_MAP:
            assert server._model_to_provider(alias) == alias


class TestModelListing:
    async def test_it_lists_every_provider_alias(self, monkeypatch):
        server = _load_server(monkeypatch)
        from agentpipe._agent import _PROVIDER_MAP

        listed = {entry["id"] for entry in (await server.openai_models())["data"]}
        assert set(_PROVIDER_MAP) <= listed
        assert "opencode/big-pickle" in listed
