from unittest.mock import AsyncMock, patch

import pytest

from agentpipe._agent import DEFAULT_CWD, DEFAULT_MODELS, Agent
from agentpipe._session import AgentSession
from agentpipe.providers.claude import ClaudeProvider


class TestAgentConstruction:
    def test_create_claude_agent_default_model(self):
        agent = Agent("claude")
        assert agent.provider == "claude"
        assert agent.model == "sonnet"
        assert agent.cwd == "/tmp"

    def test_create_gemini_agent_default_model(self):
        agent = Agent("gemini")
        assert agent.provider == "gemini"
        assert agent.model == "gemini-2.5-flash"

    def test_create_opencode_agent_default_model(self):
        agent = Agent("opencode")
        assert agent.provider == "opencode"
        assert agent.model == "opencode/gemini-3-flash"

    def test_create_agent_custom_model(self):
        agent = Agent("claude", model="haiku")
        assert agent.model == "haiku"

    def test_create_agent_custom_cwd(self):
        agent = Agent("gemini", cwd="/home/user/project")
        assert agent.cwd == "/home/user/project"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            Agent("nonexistent")

    def test_default_models_mapping(self):
        assert "claude" in DEFAULT_MODELS
        assert "gemini" in DEFAULT_MODELS
        assert "opencode" in DEFAULT_MODELS

    def test_default_cwd(self):
        assert DEFAULT_CWD == "/tmp"


class TestAgentSession:
    def test_session_context_manager(self):
        provider = ClaudeProvider(model="sonnet")
        session = AgentSession(provider)
        assert session.session_id is None


class TestAgentSessionResume:
    @pytest.mark.asyncio
    async def test_session_id_preserved_across_calls(self):
        provider = ClaudeProvider()
        session = AgentSession(provider)

        mock_stdout = '{"type":"system","session_id":"sess-1"}\n{"type":"result","result":"ok","usage":{}}\n'

        with patch.object(session, "_executor") as mock_executor:
            mock_executor.run = AsyncMock(return_value=(mock_stdout, ""))
            result = await session.generate_full("test")
            assert session.session_id == "sess-1"
            assert result.text == "ok"

    @pytest.mark.asyncio
    async def test_resume_flag_in_second_call(self):
        provider = ClaudeProvider()
        session = AgentSession(provider)

        first_stdout = '{"type":"system","session_id":"sess-1"}\n{"type":"result","result":"ok","usage":{}}\n'

        with patch.object(session, "_executor") as mock_executor:
            mock_executor.run = AsyncMock(return_value=(first_stdout, ""))

            await session.generate_full("test")
            first_cmd = mock_executor.run.call_args[0][0].argv
            assert "--resume" not in first_cmd

            second_stdout = '{"type":"result","result":"ok2","usage":{}}\n'
            mock_executor.run = AsyncMock(return_value=(second_stdout, ""))
            await session.generate_full("test2")
            second_cmd = mock_executor.run.call_args[0][0].argv
            assert "--resume" in second_cmd
            resume_idx = second_cmd.index("--resume")
            assert second_cmd[resume_idx + 1] == "sess-1"


class TestAgentFacade:
    def test_session_creates_agent_session(self):
        agent = Agent("claude")
        session = agent.session(timeout=600)
        assert isinstance(session, AgentSession)

    def test_session_uses_default_cwd(self):
        agent = Agent("claude")
        session = agent.session()
        assert session._cwd == "/tmp"

    def test_session_override_cwd(self):
        agent = Agent("claude", cwd="/home/user/project")
        session = agent.session()
        assert session._cwd == "/home/user/project"

    def test_session_per_call_cwd_override(self):
        agent = Agent("claude")
        session = agent.session(cwd="/custom/path")
        assert session._cwd == "/custom/path"
