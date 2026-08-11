"""Stateless mode and the safety of the anonymous OpenAI surface.

These assert against a real ``Agent`` and the command line its provider builds,
because that is what the CLI actually receives. Asserting on a mocked Agent
proves nothing: a mock accepts any constructor argument and reports whatever
the test set by hand.
"""
import importlib
import sys

import pytest

pytest.importorskip("fastapi")

from agentpipe import Agent
from agentpipe._types import ApprovalMode


def _load_server(monkeypatch, **env):
    """Import agentpipe.server with the given environment."""
    for key in ("AGENTPIPE_STATELESS", "AGENTPIPE_OPENAI_APPROVAL",
                "AGENTPIPE_MAX_CONCURRENCY"):
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

    def test_openai_paths_never_resume(self, monkeypatch):
        server = _load_server(monkeypatch, AGENTPIPE_STATELESS="1")
        for fn in (server._openai_complete, server._openai_stream):
            source = __import__("inspect").getsource(fn)
            assert "not _STATELESS" in source, fn.__name__
