"""Tests for Agent helper methods — auth, sessions, MCP, extensions, etc.

All tests mock the executor layer; no live CLI calls (per AGENTS.md).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from agentpipe._agent import Agent, _resolve_provider
from agentpipe._executor import AgentProcessError
from agentpipe._types import (
    ApprovalMode,
    AuthStatus,
    EffortLevel,
    GenerationResult,
    HttpMcpServer,
)


class TestResolveProvider:
    def test_resolve_known(self):
        prov = _resolve_provider("claude")
        assert prov.binary_name == "claude"

    def test_resolve_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            _resolve_provider("nonexistent")


class TestAgentPostInit:
    def test_mcp_servers_forwarded(self):
        mcp = HttpMcpServer(name="test", url="http://localhost:8080")
        agent = Agent("claude", mcp_servers=[mcp])
        assert agent.mcp_servers == [mcp]

    def test_approval_mode_forwarded(self):
        agent = Agent("claude", approval_mode=ApprovalMode.YOLO)
        assert agent.approval_mode == ApprovalMode.YOLO

    def test_max_budget_forwarded(self):
        agent = Agent("claude", max_budget_usd=5.0)
        assert agent.max_budget_usd == 5.0

    def test_system_prompt_forwarded(self):
        agent = Agent("claude", system_prompt="Be helpful")
        assert agent.system_prompt == "Be helpful"

    def test_append_system_prompt_forwarded(self):
        agent = Agent("claude", append_system_prompt="Be brief")
        assert agent.append_system_prompt == "Be brief"

    def test_allowed_tools_forwarded(self):
        agent = Agent("claude", allowed_tools=["Read", "Write"])
        assert agent.allowed_tools == ["Read", "Write"]

    def test_disallowed_tools_forwarded(self):
        agent = Agent("claude", disallowed_tools=["Bash"])
        assert agent.disallowed_tools == ["Bash"]

    def test_effort_forwarded(self):
        agent = Agent("claude", effort=EffortLevel.HIGH)
        assert agent.effort == EffortLevel.HIGH

    def test_fallback_model_forwarded(self):
        agent = Agent("claude", fallback_model="haiku")
        assert agent.fallback_model == "haiku"

    def test_json_schema_forwarded(self):
        schema = {"type": "object"}
        agent = Agent("claude", json_schema=schema)
        assert agent.json_schema == schema

    def test_session_name_forwarded(self):
        agent = Agent("claude", session_name="my-session")
        assert agent.session_name == "my-session"

    def test_agent_name_forwarded(self):
        agent = Agent("claude", agent_name="coder")
        assert agent.agent_name == "coder"

    def test_sandbox_forwarded(self):
        agent = Agent("claude", sandbox=True)
        assert agent.sandbox is True

    def test_raw_output_forwarded(self):
        agent = Agent("claude", raw_output=True)
        assert agent.raw_output is True

    def test_include_dirs_forwarded(self):
        agent = Agent("claude", include_dirs=["/src"])
        assert agent.include_dirs == ["/src"]

    def test_continue_last_forwarded(self):
        agent = Agent("claude", continue_last=True)
        assert agent.continue_last is True

    def test_fork_session_forwarded(self):
        agent = Agent("claude", fork_session=True)
        assert agent.fork_session is True

    def test_files_forwarded(self):
        agent = Agent("claude", files=["a.py"])
        assert agent.files == ["a.py"]


class TestAgentGenerate:
    @pytest.mark.asyncio
    async def test_generate_returns_text(self):
        agent = Agent("claude")
        mock_stdout = '{"type":"result","result":"hello","usage":{}}\n'
        agent.executor.run = AsyncMock(return_value=(mock_stdout, ""))
        result = await agent.generate("test")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_generate_full_returns_generation_result(self):
        agent = Agent("claude")
        mock_stdout = '{"type":"result","result":"hello","usage":{"input_tokens":10,"output_tokens":5}}\n'
        agent.executor.run = AsyncMock(return_value=(mock_stdout, ""))
        result = await agent.generate_full("test")
        assert isinstance(result, GenerationResult)
        assert result.text == "hello"

    @pytest.mark.asyncio
    async def test_generate_stream_yields_events(self):
        agent = Agent("claude")

        async def mock_run_streaming(spec):
            yield ("stdout", '{"type":"assistant","content":[{"type":"text","text":"hi"}]}\n')
            yield ("stdout", '{"type":"result","result":"hi","usage":{"input_tokens":1,"output_tokens":1}}\n')

        agent.executor.run_streaming = mock_run_streaming
        events = [event async for event in agent.generate_stream("test")]
        assert len(events) > 0


class TestAgentCheckAvailable:
    @pytest.mark.asyncio
    async def test_check_available_calls_check_binary(self):
        agent = Agent("claude")
        agent.executor.check_binary = AsyncMock(return_value="/usr/bin/claude")
        path = await agent.check_available()
        assert path == "/usr/bin/claude"
        agent.executor.check_binary.assert_called_once_with("claude")


class TestAgentAuthStatus:
    @pytest.mark.asyncio
    async def test_claude_auth_status_authenticated(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(
            return_value=(json.dumps({"loggedIn": True, "email": "x@y.z", "authMethod": "oauth"}), "")
        )
        status = await agent.auth_status()
        assert isinstance(status, AuthStatus)
        assert status.authenticated is True
        assert status.provider == "claude"
        assert status.email == "x@y.z"

    @pytest.mark.asyncio
    async def test_claude_auth_status_failure(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "err", ["claude"]))
        status = await agent.auth_status()
        assert status.authenticated is False

    @pytest.mark.asyncio
    async def test_gemini_auth_status_ok(self):
        agent = Agent("gemini")
        agent.executor.run = AsyncMock(return_value=("gemini 1.0", ""))
        status = await agent.auth_status()
        assert status.authenticated is True
        assert status.provider == "gemini"

    @pytest.mark.asyncio
    async def test_gemini_auth_status_fail(self):
        agent = Agent("gemini")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["gemini"]))
        status = await agent.auth_status()
        assert status.authenticated is False

    @pytest.mark.asyncio
    async def test_opencode_auth_status_ok(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("provider-list", ""))
        status = await agent.auth_status()
        assert status.authenticated is True
        assert status.provider == "opencode"

    @pytest.mark.asyncio
    async def test_opencode_auth_status_fail(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["opencode"]))
        status = await agent.auth_status()
        assert status.authenticated is False

    @pytest.mark.asyncio
    async def test_unsupported_provider_auth_status(self):
        agent = Agent("aider")
        status = await agent.auth_status()
        assert status.authenticated is False
        assert status.provider == "aider"


class TestAgentAuthLogin:
    @pytest.mark.asyncio
    async def test_claude_auth_login_ok(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(return_value=("", ""))
        status = await agent.auth_login()
        assert status.authenticated is True

    @pytest.mark.asyncio
    async def test_claude_auth_login_with_method(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(return_value=("", ""))
        status = await agent.auth_login(method="oauth")
        assert status.method == "oauth"

    @pytest.mark.asyncio
    async def test_claude_auth_login_fail(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["claude"]))
        status = await agent.auth_login()
        assert status.authenticated is False

    @pytest.mark.asyncio
    async def test_opencode_auth_login_ok(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("", ""))
        status = await agent.auth_login()
        assert status.authenticated is True

    @pytest.mark.asyncio
    async def test_opencode_auth_login_fail(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["opencode"]))
        status = await agent.auth_login()
        assert status.authenticated is False

    @pytest.mark.asyncio
    async def test_unsupported_auth_login_raises(self):
        agent = Agent("aider")
        with pytest.raises(NotImplementedError):
            await agent.auth_login()


class TestAgentAuthLogout:
    @pytest.mark.asyncio
    async def test_claude_auth_logout_ok(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(return_value=("", ""))
        status = await agent.auth_logout()
        assert status.authenticated is False
        assert status.provider == "claude"

    @pytest.mark.asyncio
    async def test_claude_auth_logout_fail(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["claude"]))
        status = await agent.auth_logout()
        assert status.authenticated is False

    @pytest.mark.asyncio
    async def test_opencode_auth_logout_ok(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("", ""))
        status = await agent.auth_logout()
        assert status.authenticated is False
        assert status.provider == "opencode"

    @pytest.mark.asyncio
    async def test_opencode_auth_logout_fail(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["opencode"]))
        status = await agent.auth_logout()
        assert status.authenticated is False

    @pytest.mark.asyncio
    async def test_unsupported_auth_logout_raises(self):
        agent = Agent("aider")
        with pytest.raises(NotImplementedError):
            await agent.auth_logout()


class TestAgentListSessions:
    @pytest.mark.asyncio
    async def test_gemini_list_sessions(self):
        agent = Agent("gemini")
        agent.executor.run = AsyncMock(return_value=("sess-1\nsess-2\n", ""))
        sessions = await agent.list_sessions()
        assert len(sessions) == 2
        assert sessions[0].session_id == "sess-1"
        assert sessions[0].provider == "gemini"

    @pytest.mark.asyncio
    async def test_gemini_list_sessions_fail(self):
        agent = Agent("gemini")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["gemini"]))
        sessions = await agent.list_sessions()
        assert sessions == []

    @pytest.mark.asyncio
    async def test_opencode_list_sessions(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("sess-a\nsess-b\n", ""))
        sessions = await agent.list_sessions()
        assert len(sessions) == 2
        assert sessions[0].provider == "opencode"

    @pytest.mark.asyncio
    async def test_opencode_list_sessions_fail(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["opencode"]))
        sessions = await agent.list_sessions()
        assert sessions == []

    @pytest.mark.asyncio
    async def test_unsupported_list_sessions_raises(self):
        agent = Agent("aider")
        with pytest.raises(NotImplementedError):
            await agent.list_sessions()


class TestAgentDeleteSession:
    @pytest.mark.asyncio
    async def test_opencode_delete_session_ok(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("", ""))
        result = await agent.delete_session("sess-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_opencode_delete_session_fail(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["opencode"]))
        result = await agent.delete_session("sess-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_unsupported_delete_session_raises(self):
        agent = Agent("aider")
        with pytest.raises(NotImplementedError):
            await agent.delete_session("sess-1")


class TestAgentExportSession:
    @pytest.mark.asyncio
    async def test_opencode_export_session_ok(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=('{"data":"exported"}', ""))
        export = await agent.export_session("sess-1")
        assert export.session_id == "sess-1"
        assert export.data == '{"data":"exported"}'

    @pytest.mark.asyncio
    async def test_opencode_export_session_fail(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["opencode"]))
        export = await agent.export_session("sess-1")
        assert export.data == ""

    @pytest.mark.asyncio
    async def test_unsupported_export_session_raises(self):
        agent = Agent("aider")
        with pytest.raises(NotImplementedError):
            await agent.export_session("sess-1")


class TestAgentImportSession:
    @pytest.mark.asyncio
    async def test_opencode_import_session_ok(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("new-sess-id\n", ""))
        result = await agent.import_session('{"data":"..."}')
        assert result == "new-sess-id"

    @pytest.mark.asyncio
    async def test_opencode_import_session_empty(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(return_value=("\n", ""))
        result = await agent.import_session('{"data":"..."}')
        assert result is None

    @pytest.mark.asyncio
    async def test_opencode_import_session_fail(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["opencode"]))
        result = await agent.import_session('{"data":"..."}')
        assert result is None

    @pytest.mark.asyncio
    async def test_unsupported_import_session_raises(self):
        agent = Agent("aider")
        with pytest.raises(NotImplementedError):
            await agent.import_session("{}")


class TestAgentMcpAdd:
    @pytest.mark.asyncio
    async def test_claude_mcp_add_url(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(return_value=("", ""))
        result = await agent.mcp_add("test-server", url="http://localhost:8080")
        assert result is True

    @pytest.mark.asyncio
    async def test_claude_mcp_add_command(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(return_value=("", ""))
        result = await agent.mcp_add("test-server", command="npx", args=["-y", "server"])
        assert result is True

    @pytest.mark.asyncio
    async def test_claude_mcp_add_with_headers_and_scope(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(return_value=("", ""))
        result = await agent.mcp_add(
            "test-server",
            url="http://localhost:8080",
            headers={"Auth": "Bearer tok"},
            scope="project",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_claude_mcp_add_no_url_no_command(self):
        agent = Agent("claude")
        result = await agent.mcp_add("test-server")
        assert result is False

    @pytest.mark.asyncio
    async def test_claude_mcp_add_fail(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["claude"]))
        result = await agent.mcp_add("test-server", url="http://localhost")
        assert result is False

    @pytest.mark.asyncio
    async def test_opencode_mcp_add_url(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("", ""))
        result = await agent.mcp_add("test-server", url="http://localhost:9090")
        assert result is True

    @pytest.mark.asyncio
    async def test_opencode_mcp_add_command_with_env(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("", ""))
        result = await agent.mcp_add("srv", command="node", args=["server.js"], env={"PORT": "3000"})
        assert result is True

    @pytest.mark.asyncio
    async def test_opencode_mcp_add_no_url_no_command(self):
        agent = Agent("opencode-free")
        result = await agent.mcp_add("test-server")
        assert result is False

    @pytest.mark.asyncio
    async def test_unsupported_mcp_add_raises(self):
        agent = Agent("aider")
        with pytest.raises(NotImplementedError):
            await agent.mcp_add("srv", url="http://x")


class TestAgentMcpRemove:
    @pytest.mark.asyncio
    async def test_claude_mcp_remove_ok(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(return_value=("", ""))
        result = await agent.mcp_remove("test-server")
        assert result is True

    @pytest.mark.asyncio
    async def test_claude_mcp_remove_with_scope(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(return_value=("", ""))
        result = await agent.mcp_remove("test-server", scope="user")
        assert result is True

    @pytest.mark.asyncio
    async def test_claude_mcp_remove_fail(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["claude"]))
        result = await agent.mcp_remove("test-server")
        assert result is False

    @pytest.mark.asyncio
    async def test_opencode_mcp_remove_ok(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("", ""))
        result = await agent.mcp_remove("test-server")
        assert result is True

    @pytest.mark.asyncio
    async def test_opencode_mcp_remove_fail(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["opencode"]))
        result = await agent.mcp_remove("test-server")
        assert result is False

    @pytest.mark.asyncio
    async def test_unsupported_mcp_remove_raises(self):
        agent = Agent("aider")
        with pytest.raises(NotImplementedError):
            await agent.mcp_remove("srv")


class TestAgentMcpList:
    @pytest.mark.asyncio
    async def test_claude_mcp_list(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(return_value=("server-a\nserver-b\n", ""))
        servers = await agent.mcp_list()
        assert len(servers) == 2
        assert servers[0].name == "server-a"
        assert servers[1].name == "server-b"

    @pytest.mark.asyncio
    async def test_claude_mcp_list_filters_no_prefix(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(return_value=("No servers configured\n", ""))
        servers = await agent.mcp_list()
        assert servers == []

    @pytest.mark.asyncio
    async def test_claude_mcp_list_fail(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["claude"]))
        servers = await agent.mcp_list()
        assert servers == []

    @pytest.mark.asyncio
    async def test_opencode_mcp_list(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("srv-1\nsrv-2\n", ""))
        servers = await agent.mcp_list()
        assert len(servers) == 2

    @pytest.mark.asyncio
    async def test_opencode_mcp_list_fail(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["opencode"]))
        servers = await agent.mcp_list()
        assert servers == []

    @pytest.mark.asyncio
    async def test_unsupported_mcp_list_raises(self):
        agent = Agent("aider")
        with pytest.raises(NotImplementedError):
            await agent.mcp_list()


class TestAgentListModels:
    @pytest.mark.asyncio
    async def test_opencode_list_models(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("model-1\nmodel-2\n", ""))
        models = await agent.list_models()
        assert len(models) == 2
        assert models[0].id == "model-1"

    @pytest.mark.asyncio
    async def test_opencode_list_models_fail(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["opencode"]))
        models = await agent.list_models()
        assert models == []

    @pytest.mark.asyncio
    async def test_unsupported_list_models_raises(self):
        agent = Agent("aider")
        with pytest.raises(NotImplementedError):
            await agent.list_models()


class TestAgentStats:
    @pytest.mark.asyncio
    async def test_opencode_stats(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("stats data", ""))
        result = await agent.stats()
        assert result == {"raw": "stats data"}

    @pytest.mark.asyncio
    async def test_opencode_stats_with_days(self):
        agent = Agent("opencode-free")
        agent.executor.run = AsyncMock(return_value=("data", ""))
        result = await agent.stats(days=7)
        assert result == {"raw": "data"}
        spec = agent.executor.run.call_args[0][0]
        assert "--days" in spec.argv
        assert "7" in spec.argv

    @pytest.mark.asyncio
    async def test_opencode_stats_fail(self):
        agent = Agent("opencode")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["opencode"]))
        result = await agent.stats()
        assert result == {"raw": ""}

    @pytest.mark.asyncio
    async def test_unsupported_stats_raises(self):
        agent = Agent("aider")
        with pytest.raises(NotImplementedError):
            await agent.stats()


class TestAgentListExtensions:
    @pytest.mark.asyncio
    async def test_gemini_list_extensions(self):
        agent = Agent("gemini")
        agent.executor.run = AsyncMock(return_value=("ext-a\next-b\n", ""))
        exts = await agent.list_extensions()
        assert len(exts) == 2
        assert exts[0].name == "ext-a"
        assert exts[1].name == "ext-b"

    @pytest.mark.asyncio
    async def test_gemini_list_extensions_fail(self):
        agent = Agent("gemini")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["gemini"]))
        exts = await agent.list_extensions()
        assert exts == []

    @pytest.mark.asyncio
    async def test_unsupported_list_extensions_raises(self):
        agent = Agent("claude")
        with pytest.raises(NotImplementedError):
            await agent.list_extensions()


class TestAgentDoctor:
    @pytest.mark.asyncio
    async def test_claude_doctor_ok(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(return_value=("doctor output", ""))
        result = await agent.doctor()
        assert result == {"raw": "doctor output"}

    @pytest.mark.asyncio
    async def test_claude_doctor_fail(self):
        agent = Agent("claude")
        agent.executor.run = AsyncMock(side_effect=AgentProcessError(1, "", ["claude"]))
        result = await agent.doctor()
        assert result == {"raw": ""}

    @pytest.mark.asyncio
    async def test_unsupported_doctor_raises(self):
        agent = Agent("gemini")
        with pytest.raises(NotImplementedError):
            await agent.doctor()
