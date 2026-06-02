import json

from agentpipe._types import EffortLevel
from agentpipe.providers.claude import ClaudeProvider, ClaudeSonnetProvider
from agentpipe.providers.gemini import GeminiFlashProvider, GeminiProvider
from agentpipe.providers.opencode import (
    OpencodeFreeProvider,
    OpencodeGoProvider,
    OpencodeProvider,
    OpencodeZenProvider,
)


class TestClaudeSystemPrompt:
    def test_system_prompt_flag(self):
        p = ClaudeProvider(model="sonnet", system_prompt="You are a helper")
        cmd = p.build_command("test")
        assert "--system-prompt" in cmd
        idx = cmd.index("--system-prompt")
        assert cmd[idx + 1] == "You are a helper"

    def test_append_system_prompt_flag(self):
        p = ClaudeProvider(model="sonnet", append_system_prompt="Be concise")
        cmd = p.build_command("test")
        assert "--append-system-prompt" in cmd
        idx = cmd.index("--append-system-prompt")
        assert cmd[idx + 1] == "Be concise"

    def test_no_system_prompt_no_flag(self):
        p = ClaudeProvider(model="sonnet")
        cmd = p.build_command("test")
        assert "--system-prompt" not in cmd
        assert "--append-system-prompt" not in cmd


class TestClaudeToolAllowDeny:
    def test_allowed_tools(self):
        p = ClaudeProvider(model="sonnet", allowed_tools=["Read", "Write"])
        cmd = p.build_command("test")
        assert cmd.count("--allowedTools") == 2
        idx1 = cmd.index("--allowedTools")
        assert cmd[idx1 + 1] == "Read"
        idx2 = cmd.index("--allowedTools", idx1 + 2)
        assert cmd[idx2 + 1] == "Write"

    def test_disallowed_tools(self):
        p = ClaudeProvider(model="sonnet", disallowed_tools=["Bash", "rm"])
        cmd = p.build_command("test")
        assert cmd.count("--disallowedTools") == 2

    def test_no_tools_no_flags(self):
        p = ClaudeProvider(model="sonnet")
        cmd = p.build_command("test")
        assert "--allowedTools" not in cmd
        assert "--disallowedTools" not in cmd


class TestClaudeEffort:
    def test_effort_level(self):
        p = ClaudeProvider(model="sonnet", effort="high")
        cmd = p.build_command("test")
        assert "--effort" in cmd
        idx = cmd.index("--effort")
        assert cmd[idx + 1] == "high"

    def test_no_effort_no_flag(self):
        p = ClaudeProvider(model="sonnet")
        cmd = p.build_command("test")
        assert "--effort" not in cmd


class TestClaudeFallbackModel:
    def test_fallback_model_flag(self):
        p = ClaudeProvider(model="sonnet", fallback_model="haiku")
        cmd = p.build_command("test")
        assert "--fallback-model" in cmd
        idx = cmd.index("--fallback-model")
        assert cmd[idx + 1] == "haiku"

    def test_no_fallback_no_flag(self):
        p = ClaudeProvider(model="sonnet")
        cmd = p.build_command("test")
        assert "--fallback-model" not in cmd


class TestClaudeJsonSchema:
    def test_json_schema_adds_output_format(self):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        p = ClaudeProvider(model="sonnet", json_schema=schema)
        cmd = p.build_command("test")
        assert "--json-schema" in cmd
        idx = cmd.index("--json-schema")
        assert json.loads(cmd[idx + 1]) == schema
        assert "--output-format" in cmd
        of_idx = cmd.index("--output-format")
        assert cmd[of_idx + 1] == "json"

    def test_no_schema_no_flag(self):
        p = ClaudeProvider(model="sonnet")
        cmd = p.build_command("test")
        assert "--json-schema" not in cmd


class TestClaudeSandbox:
    def test_sandbox_flag(self):
        p = ClaudeProvider(model="sonnet", sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_no_sandbox_no_flag(self):
        p = ClaudeProvider(model="sonnet")
        cmd = p.build_command("test")
        assert "--sandbox" not in cmd


class TestClaudeRawOutput:
    def test_raw_output_no_verbose(self):
        p = ClaudeProvider(model="sonnet", raw_output=True)
        cmd = p.build_command("test")
        assert "--verbose" not in cmd
        assert "--output-format" in cmd

    def test_default_has_verbose(self):
        p = ClaudeProvider(model="sonnet")
        cmd = p.build_command("test")
        assert "--verbose" in cmd


class TestClaudeAgentName:
    def test_agent_name_flag(self):
        p = ClaudeProvider(model="sonnet", agent_name="coder")
        cmd = p.build_command("test")
        assert "--agent" in cmd
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "coder"


class TestClaudeIncludeDirs:
    def test_include_dirs(self):
        p = ClaudeProvider(model="sonnet", include_dirs=["/src", "/lib"])
        cmd = p.build_command("test")
        assert cmd.count("--add-dir") == 2
        idx1 = cmd.index("--add-dir")
        assert cmd[idx1 + 1] == "/src"

    def test_no_include_dirs_no_flag(self):
        p = ClaudeProvider(model="sonnet")
        cmd = p.build_command("test")
        assert "--add-dir" not in cmd


class TestClaudeSubclassPassthrough:
    def test_sonnet_passes_kwargs(self):
        p = ClaudeSonnetProvider(system_prompt="Be helpful", sandbox=True)
        cmd = p.build_command("test")
        assert "--system-prompt" in cmd
        assert "--sandbox" in cmd
        assert "--model" in cmd


class TestGeminiNewFeatures:
    def test_sandbox_flag(self):
        p = GeminiProvider(model="gemini-2.5-flash", sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_include_dirs(self):
        p = GeminiProvider(model="gemini-2.5-flash", include_dirs=["/src"])
        cmd = p.build_command("test")
        assert "--include-directories" in cmd
        idx = cmd.index("--include-directories")
        assert cmd[idx + 1] == "/src"

    def test_no_sandbox_no_flag(self):
        p = GeminiProvider(model="gemini-2.5-flash")
        cmd = p.build_command("test")
        assert "--sandbox" not in cmd

    def test_flash_subclass_passthrough(self):
        p = GeminiFlashProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd


class TestOpencodeNewFeatures:
    def test_sandbox_flag(self):
        p = OpencodeProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_include_dirs(self):
        p = OpencodeProvider(include_dirs=["/src"])
        cmd = p.build_command("test")
        assert "--dir" in cmd
        idx = cmd.index("--dir")
        assert cmd[idx + 1] == "/src"

    def test_no_sandbox_no_flag(self):
        p = OpencodeProvider()
        cmd = p.build_command("test")
        assert "--sandbox" not in cmd

    def test_free_subclass_passthrough(self):
        p = OpencodeFreeProvider(sandbox=True, include_dirs=["/app"])
        cmd = p.build_command("test")
        assert "--sandbox" in cmd
        assert "--dir" in cmd

    def test_zen_subclass_passthrough(self):
        p = OpencodeZenProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_go_subclass_passthrough(self):
        p = OpencodeGoProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd


class TestEffortLevelEnum:
    def test_values(self):
        assert EffortLevel.LOW.value == "low"
        assert EffortLevel.MEDIUM.value == "medium"
        assert EffortLevel.HIGH.value == "high"
        assert EffortLevel.VERY_HIGH.value == "xhigh"
        assert EffortLevel.MAX.value == "max"

    def test_string_enum(self):
        assert EffortLevel("low") == EffortLevel.LOW
        assert EffortLevel("xhigh") == EffortLevel.VERY_HIGH


class TestMcpServerInfo:
    def test_frozen(self):
        from agentpipe._types import McpServerInfo

        m = McpServerInfo(name="github", type="stdio", command="npx")
        assert m.name == "github"
        assert m.type == "stdio"
        assert m.url is None

    def test_defaults(self):
        from agentpipe._types import McpServerInfo

        m = McpServerInfo(name="test")
        assert m.type is None
        assert m.enabled is None


class TestExtensionInfo:
    def test_frozen(self):
        from agentpipe._types import ExtensionInfo

        e = ExtensionInfo(name="search", version="1.0")
        assert e.name == "search"
        assert e.version == "1.0"

    def test_defaults(self):
        from agentpipe._types import ExtensionInfo

        e = ExtensionInfo(name="test")
        assert e.version is None


class TestSessionExport:
    def test_frozen(self):
        from agentpipe._types import SessionExport

        s = SessionExport(session_id="abc", data='{"key": "val"}')
        assert s.session_id == "abc"
        assert s.format == "json"

    def test_default_format(self):
        from agentpipe._types import SessionExport

        s = SessionExport(session_id="x", data="")
        assert s.format == "json"


class TestAgentNewFieldsInAgentDataclass:
    def test_system_prompt(self):
        from agentpipe._agent import Agent

        agent = Agent("claude", system_prompt="Be helpful")
        assert agent.system_prompt == "Be helpful"
        assert agent._provider_instance._system_prompt == "Be helpful"

    def test_effort(self):
        from agentpipe._agent import Agent
        from agentpipe._types import EffortLevel

        agent = Agent("claude", effort=EffortLevel.HIGH)
        assert agent.effort == EffortLevel.HIGH
        assert agent._provider_instance._effort == "high"

    def test_sandbox(self):
        from agentpipe._agent import Agent

        agent = Agent("opencode", sandbox=True)
        assert agent.sandbox is True
        assert agent._provider_instance._sandbox is True

    def test_include_dirs(self):
        from agentpipe._agent import Agent

        agent = Agent("gemini", include_dirs=["/src"])
        assert agent.include_dirs == ["/src"]
        assert agent._provider_instance._include_dirs == ["/src"]

    def test_defaults_are_none(self):
        from agentpipe._agent import Agent

        agent = Agent("claude")
        assert agent.system_prompt is None
        assert agent.append_system_prompt is None
        assert agent.allowed_tools is None
        assert agent.disallowed_tools is None
        assert agent.effort is None
        assert agent.fallback_model is None
        assert agent.json_schema is None
        assert agent.session_name is None
        assert agent.agent_name is None
        assert agent.sandbox is False
        assert agent.raw_output is False
        assert agent.include_dirs is None
        assert agent.continue_last is False
        assert agent.fork_session is False
        assert agent.files is None


class TestOpencodeApprovalMode:
    def test_yolo_mode(self):
        from agentpipe._types import ApprovalMode

        p = OpencodeProvider(approval_mode=ApprovalMode.YOLO)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_bypass_mode(self):
        from agentpipe._types import ApprovalMode

        p = OpencodeProvider(approval_mode=ApprovalMode.BYPASS)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_default_mode_no_skip(self):
        from agentpipe._types import ApprovalMode

        p = OpencodeProvider(approval_mode=ApprovalMode.DEFAULT)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" not in cmd

    def test_no_approval_mode_skips_permissions(self):
        p = OpencodeProvider()
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd


class TestOpencodeContinueAndFork:
    def test_continue_flag(self):
        p = OpencodeProvider(continue_last=True)
        cmd = p.build_command("test")
        assert "--continue" in cmd

    def test_fork_flag(self):
        p = OpencodeProvider(fork_session=True, continue_last=True)
        cmd = p.build_command("test")
        assert "--fork" in cmd

    def test_fork_without_context_still_emits(self):
        p = OpencodeProvider(fork_session=True)
        cmd = p.build_command("test")
        assert "--fork" in cmd


class TestOpencodeAgentName:
    def test_agent_flag(self):
        p = OpencodeProvider(agent_name="reviewer")
        cmd = p.build_command("test")
        assert "--agent" in cmd
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "reviewer"


class TestOpencodeSessionName:
    def test_title_flag(self):
        p = OpencodeProvider(session_name="my-session")
        cmd = p.build_command("test")
        assert "--title" in cmd
        idx = cmd.index("--title")
        assert cmd[idx + 1] == "my-session"


class TestOpencodeEffort:
    def test_effort_variant(self):
        p = OpencodeProvider(effort="high")
        cmd = p.build_command("test")
        assert "--variant" in cmd
        idx = cmd.index("--variant")
        assert cmd[idx + 1] == "high"

    def test_effort_mapped_variant(self):
        p = OpencodeProvider(effort="low")
        cmd = p.build_command("test")
        idx = cmd.index("--variant")
        assert cmd[idx + 1] == "minimal"

    def test_no_effort_no_flag(self):
        p = OpencodeProvider()
        cmd = p.build_command("test")
        assert "--variant" not in cmd


class TestOpencodeFiles:
    def test_files_flag(self):
        p = OpencodeProvider(files=["/tmp/a.txt", "/tmp/b.py"])
        cmd = p.build_command("test")
        assert cmd.count("--file") == 2


class TestGeminiApprovalMode:
    def test_yolo_flag(self):
        from agentpipe._types import ApprovalMode

        p = GeminiProvider(model="gemini-2.5-flash", approval_mode=ApprovalMode.YOLO)
        cmd = p.build_command("test")
        assert "--yolo" in cmd

    def test_bypass_is_yolo(self):
        from agentpipe._types import ApprovalMode

        p = GeminiProvider(model="gemini-2.5-flash", approval_mode=ApprovalMode.BYPASS)
        cmd = p.build_command("test")
        assert "--yolo" in cmd

    def test_plan_mode(self):
        from agentpipe._types import ApprovalMode

        p = GeminiProvider(model="gemini-2.5-flash", approval_mode=ApprovalMode.PLAN)
        cmd = p.build_command("test")
        assert "--approval-mode" in cmd
        idx = cmd.index("--approval-mode")
        assert cmd[idx + 1] == "plan"

    def test_auto_edit_mode(self):
        from agentpipe._types import ApprovalMode

        p = GeminiProvider(model="gemini-2.5-flash", approval_mode=ApprovalMode.AUTO_EDIT)
        cmd = p.build_command("test")
        assert "--approval-mode" in cmd
        idx = cmd.index("--approval-mode")
        assert cmd[idx + 1] == "auto_edit"

    def test_default_approval_mode(self):
        from agentpipe._types import ApprovalMode

        p = GeminiProvider(model="gemini-2.5-flash", approval_mode=ApprovalMode.DEFAULT)
        cmd = p.build_command("test")
        assert "--approval-mode" in cmd
        assert "--yolo" not in cmd

    def test_no_approval_mode_no_yolo(self):
        p = GeminiProvider(model="gemini-2.5-flash")
        cmd = p.build_command("test")
        assert "--yolo" not in cmd


class TestGeminiAllowedTools:
    def test_allowed_tools(self):
        p = GeminiProvider(model="gemini-2.5-flash", allowed_tools=["Read", "Write"])
        cmd = p.build_command("test")
        assert cmd.count("--allowed-tools") == 2


class TestGeminiRawOutput:
    def test_raw_output_flags(self):
        p = GeminiProvider(model="gemini-2.5-flash", raw_output=True)
        cmd = p.build_command("test")
        assert "--raw-output" in cmd
        assert "--output-format" in cmd
        of_idx = cmd.index("--output-format")
        assert cmd[of_idx + 1] == "json"


class TestGeminiExtensions:
    def test_extensions_flag(self):
        p = GeminiProvider(model="gemini-2.5-flash", extensions=["search", "code"])
        cmd = p.build_command("test")
        assert cmd.count("--extensions") == 2


class TestClaudeContinueAndFork:
    def test_continue_flag(self):
        p = ClaudeProvider(model="sonnet", continue_last=True)
        cmd = p.build_command("test")
        assert "--continue" in cmd

    def test_fork_session_flag(self):
        p = ClaudeProvider(model="sonnet", fork_session=True, continue_last=True)
        cmd = p.build_command("test")
        assert "--fork-session" in cmd

    def test_fork_without_resume_no_flag(self):
        p = ClaudeProvider(model="sonnet", fork_session=True)
        cmd = p.build_command("test")
        assert "--fork-session" not in cmd

    def test_session_name_flag(self):
        p = ClaudeProvider(model="sonnet", session_name="my-session")
        cmd = p.build_command("test")
        assert "--name" in cmd
        idx = cmd.index("--name")
        assert cmd[idx + 1] == "my-session"

    def test_files_flag(self):
        p = ClaudeProvider(model="sonnet", files=["file_abc:doc.txt"])
        cmd = p.build_command("test")
        assert cmd.count("--file") == 1


class TestAgentForwardingNewFields:
    def test_continue_last_forwarded(self):
        from agentpipe._agent import Agent

        agent = Agent("opencode", continue_last=True)
        assert agent._provider_instance._continue_last is True

    def test_fork_session_forwarded(self):
        from agentpipe._agent import Agent

        agent = Agent("opencode", fork_session=True)
        assert agent._provider_instance._fork_session is True

    def test_files_forwarded(self):
        from agentpipe._agent import Agent

        agent = Agent("claude", files=["file_abc:doc.txt"])
        assert agent._provider_instance._files == ["file_abc:doc.txt"]

    def test_approval_mode_opencode(self):
        from agentpipe._agent import Agent
        from agentpipe._types import ApprovalMode

        agent = Agent("opencode", approval_mode=ApprovalMode.YOLO)
        assert agent._provider_instance._approval_mode == ApprovalMode.YOLO
        cmd = agent._provider_instance.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_approval_mode_gemini(self):
        from agentpipe._agent import Agent
        from agentpipe._types import ApprovalMode

        agent = Agent("gemini", approval_mode=ApprovalMode.PLAN)
        assert agent._provider_instance._approval_mode == ApprovalMode.PLAN
        cmd = agent._provider_instance.build_command("test")
        assert "--approval-mode" in cmd


class TestVibeProviderConstruction:
    def test_default_model(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider()
        assert p.model == "mistral-large-latest"
        assert p.binary_name == "vibe"

    def test_custom_model(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider(model="mistral-medium-latest")
        assert p.model == "mistral-medium-latest"

    def test_prompt_flag(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider()
        cmd = p.build_command("hello")
        assert "--prompt" in cmd
        assert "hello" in cmd
        assert "--output" in cmd
        out_idx = cmd.index("--output")
        assert cmd[out_idx + 1] == "streaming"

    def test_continue_flag(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider(continue_last=True)
        cmd = p.build_command("test")
        assert "--continue" in cmd

    def test_resume_flag(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider()
        cmd = p.build_command("test", session_id="abc123")
        assert "--resume" in cmd
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "abc123"

    def test_approval_mode_plan(self):
        from agentpipe._types import ApprovalMode
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider(approval_mode=ApprovalMode.PLAN)
        cmd = p.build_command("test")
        assert "--agent" in cmd
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "plan"

    def test_approval_mode_yolo(self):
        from agentpipe._types import ApprovalMode
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider(approval_mode=ApprovalMode.YOLO)
        cmd = p.build_command("test")
        assert "--agent" in cmd
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "auto-approve"

    def test_sandbox_flag(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_include_dirs(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider(include_dirs=["/src"])
        cmd = p.build_command("test")
        assert "--add-dir" in cmd
        idx = cmd.index("--add-dir")
        assert cmd[idx + 1] == "/src"

    def test_enabled_tools(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider(allowed_tools=["read_file", "grep"])
        cmd = p.build_command("test")
        assert cmd.count("--enabled-tools") == 2

    def test_max_turns(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider(max_turns=5)
        cmd = p.build_command("test")
        assert "--max-turns" in cmd
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "5"

    def test_max_price(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider(max_price=1.0)
        cmd = p.build_command("test")
        assert "--max-price" in cmd

    def test_json_output(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider()
        cmd = p.build_command("test")
        assert "--output" in cmd

    def test_parse_text_event(self):
        from agentpipe.providers.vibe import VibeProvider

        p = VibeProvider()
        events = p.parse_event_line('{"type":"text","content":"Hello"}')
        assert len(events) == 1
        assert events[0].text == "Hello"


class TestQoderProviderConstruction:
    def test_default_model(self):
        from agentpipe.providers.qoder import QoderProvider

        p = QoderProvider()
        assert p.model is None
        assert p.binary_name == "qodercli"

    def test_custom_model(self):
        from agentpipe.providers.qoder import QoderProvider

        p = QoderProvider(model="mistral-large-latest")
        assert p.model == "mistral-large-latest"

    def test_prompt_flag(self):
        from agentpipe.providers.qoder import QoderProvider

        p = QoderProvider()
        cmd = p.build_command("hello")
        assert "-p" in cmd
        assert "hello" in cmd
        assert "--output-format" in cmd

    def test_yolo_mode(self):
        from agentpipe._types import ApprovalMode
        from agentpipe.providers.qoder import QoderProvider

        p = QoderProvider(approval_mode=ApprovalMode.YOLO)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_plan_mode(self):
        from agentpipe._types import ApprovalMode
        from agentpipe.providers.qoder import QoderProvider

        p = QoderProvider(approval_mode=ApprovalMode.PLAN)
        cmd = p.build_command("test")
        assert "--permission-mode" in cmd
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "plan"

    def test_system_prompt(self):
        from agentpipe.providers.qoder import QoderProvider

        p = QoderProvider(system_prompt="Be helpful")
        cmd = p.build_command("test")
        assert "--system-prompt" in cmd

    def test_mcp_config(self):
        from agentpipe._types import HttpMcpServer
        from agentpipe.providers.qoder import QoderProvider

        p = QoderProvider(mcp_servers=[HttpMcpServer(name="docs", url="http://localhost:9000/sse")])
        cmd = p.build_command("test")
        assert "--mcp-config" in cmd

    def test_max_turns(self):
        from agentpipe.providers.qoder import QoderProvider

        p = QoderProvider(max_turns=10)
        cmd = p.build_command("test")
        assert "--max-turns" in cmd
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "10"

    def test_parse_text_event(self):
        from agentpipe.providers.qoder import QoderProvider

        p = QoderProvider()
        events = p.parse_event_line('{"type":"text","content":"Hello"}')
        assert len(events) == 1
        assert events[0].text == "Hello"


class TestAgentNewProviders:
    def test_vibe_agent(self):
        from agentpipe._agent import Agent

        agent = Agent("vibe")
        assert agent.provider == "vibe"
        assert agent.model == "mistral-large-latest"

    def test_qoder_agent(self):
        from agentpipe._agent import Agent

        agent = Agent("qoder")
        assert agent.provider == "qoder"

    def test_vibe_with_approval_mode(self):
        from agentpipe._agent import Agent
        from agentpipe._types import ApprovalMode

        agent = Agent("vibe", approval_mode=ApprovalMode.PLAN)
        cmd = agent._provider_instance.build_command("test")
        assert "--agent" in cmd

    def test_qoder_with_system_prompt(self):
        from agentpipe._agent import Agent

        agent = Agent("qoder", system_prompt="Be helpful")
        cmd = agent._provider_instance.build_command("test")
        assert "--system-prompt" in cmd


class TestAiderProviderConstruction:
    def test_default_model(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        assert p.model == "openrouter/google/gemma-4-26b-a4b-it:free"
        assert p.binary_name == "aider"

    def test_custom_model(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(model="openrouter/qwen/qwen3-coder:free")
        assert p.model == "openrouter/qwen/qwen3-coder:free"

    def test_message_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        cmd = p.build_command("hello")
        assert "--message" in cmd
        idx = cmd.index("--message")
        assert cmd[idx + 1] == "hello"

    def test_yes_always_default(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        cmd = p.build_command("test")
        assert "--yes-always" in cmd

    def test_model_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        cmd = p.build_command("test")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "openrouter/google/gemma-4-26b-a4b-it:free"

    def test_custom_model_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(model="openrouter/qwen/qwen3-coder:free")
        cmd = p.build_command("test")
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "openrouter/qwen/qwen3-coder:free"

    def test_model_override_in_build_command(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(model="openrouter/default")
        cmd = p.build_command("test", model="openrouter/override")
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "openrouter/override"

    def test_files_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(files=["main.py", "utils.py"])
        cmd = p.build_command("test")
        assert cmd.count("--file") == 2
        idx1 = cmd.index("--file")
        assert cmd[idx1 + 1] == "main.py"
        idx2 = cmd.index("--file", idx1 + 2)
        assert cmd[idx2 + 1] == "utils.py"

    def test_read_files_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(read_files=["README.md"])
        cmd = p.build_command("test")
        assert "--read" in cmd
        idx = cmd.index("--read")
        assert cmd[idx + 1] == "README.md"

    def test_architect_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(architect=True)
        cmd = p.build_command("test")
        assert "--architect" in cmd

    def test_no_architect_default(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        cmd = p.build_command("test")
        assert "--architect" not in cmd

    def test_edit_format_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(edit_format="diff")
        cmd = p.build_command("test")
        assert "--edit-format" in cmd
        idx = cmd.index("--edit-format")
        assert cmd[idx + 1] == "diff"

    def test_weak_model_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(weak_model="openrouter/gpt-4o-mini:free")
        cmd = p.build_command("test")
        assert "--weak-model" in cmd
        idx = cmd.index("--weak-model")
        assert cmd[idx + 1] == "openrouter/gpt-4o-mini:free"

    def test_reasoning_effort_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(reasoning_effort="high")
        cmd = p.build_command("test")
        assert "--reasoning-effort" in cmd
        idx = cmd.index("--reasoning-effort")
        assert cmd[idx + 1] == "high"

    def test_effort_maps_to_reasoning_effort(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(effort="high")
        cmd = p.build_command("test")
        assert "--reasoning-effort" in cmd
        idx = cmd.index("--reasoning-effort")
        assert cmd[idx + 1] == "high"

    def test_reasoning_effort_precedes_effort(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(effort="low", reasoning_effort="high")
        cmd = p.build_command("test")
        idx = cmd.index("--reasoning-effort")
        assert cmd[idx + 1] == "high"

    def test_thinking_tokens_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(thinking_tokens=8000)
        cmd = p.build_command("test")
        assert "--thinking-tokens" in cmd
        idx = cmd.index("--thinking-tokens")
        assert cmd[idx + 1] == "8000"

    def test_cache_prompts_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(cache_prompts=True)
        cmd = p.build_command("test")
        assert "--cache-prompts" in cmd

    def test_no_cache_default(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        cmd = p.build_command("test")
        assert "--cache-prompts" not in cmd

    def test_map_tokens_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(map_tokens=2048)
        cmd = p.build_command("test")
        assert "--map-tokens" in cmd
        idx = cmd.index("--map-tokens")
        assert cmd[idx + 1] == "2048"

    def test_no_git_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(git=False)
        cmd = p.build_command("test")
        assert "--no-git" in cmd

    def test_git_default(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        cmd = p.build_command("test")
        assert "--no-git" not in cmd

    def test_no_auto_commits_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(auto_commits=False)
        cmd = p.build_command("test")
        assert "--no-auto-commits" in cmd

    def test_dry_run_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(dry_run=True)
        cmd = p.build_command("test")
        assert "--dry-run" in cmd

    def test_show_diffs_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(show_diffs=True)
        cmd = p.build_command("test")
        assert "--show-diffs" in cmd

    def test_lint_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(lint=True)
        cmd = p.build_command("test")
        assert "--lint" in cmd

    def test_test_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(test=True)
        cmd = p.build_command("test")
        assert "--test" in cmd

    def test_lint_cmd_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(lint_cmd=["python: flake8", "js: eslint"])
        cmd = p.build_command("test")
        assert cmd.count("--lint-cmd") == 2
        idx1 = cmd.index("--lint-cmd")
        assert cmd[idx1 + 1] == "python: flake8"

    def test_test_cmd_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(test_cmd="pytest")
        cmd = p.build_command("test")
        assert "--test-cmd" in cmd
        idx = cmd.index("--test-cmd")
        assert cmd[idx + 1] == "pytest"

    def test_no_auto_lint_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(auto_lint=False)
        cmd = p.build_command("test")
        assert "--no-auto-lint" in cmd

    def test_auto_test_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(auto_test=True)
        cmd = p.build_command("test")
        assert "--auto-test" in cmd

    def test_api_key_env(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(api_key=["anthropic=sk-ant-xxx", "openai=sk-xxx"])
        env = p.build_env()
        assert env.get("AIDER_ANTHROPIC_API_KEY") == "sk-ant-xxx"
        assert env.get("AIDER_OPENAI_API_KEY") == "sk-xxx"
        assert "--api-key" not in p.build_command("test")

    def test_set_env_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(set_env=["OPENAI_API_BASE=http://localhost:8000"])
        cmd = p.build_command("test")
        assert "--set-env" in cmd
        idx = cmd.index("--set-env")
        assert cmd[idx + 1] == "OPENAI_API_BASE=http://localhost:8000"

    def test_timeout_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(api_timeout=120)
        cmd = p.build_command("test")
        assert "--timeout" in cmd
        idx = cmd.index("--timeout")
        assert cmd[idx + 1] == "120"

    def test_verbose_flag(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider(verbose=True)
        cmd = p.build_command("test")
        assert "-v" in cmd

    def test_no_pretty_and_no_stream(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        cmd = p.build_command("test")
        assert "--no-pretty" in cmd
        assert "--no-stream" in cmd

    def test_no_check_update_and_no_model_warnings(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        cmd = p.build_command("test")
        assert "--no-check-update" in cmd
        assert "--no-show-model-warnings" in cmd

    def test_no_session_id_support(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        cmd = p.build_command("test", session_id="abc")
        assert "--resume" not in cmd
        assert "abc" not in cmd

    def test_parse_thinking_event(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        events = p.parse_event_line("Hello world")
        assert len(events) == 1
        assert events[0].text == "Hello world"

    def test_parse_tokens_event(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        events = p.parse_event_line("Tokens: 620 sent, 19 received.")
        assert len(events) == 1
        assert events[0].input_tokens == 620
        assert events[0].output_tokens == 19

    def test_parse_header_lines_returns_empty(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        assert p.parse_event_line("Aider v0.86.2") == []
        assert p.parse_event_line("Model: openrouter/test with diff") == []
        assert p.parse_event_line("Git repo: none") == []
        assert p.parse_event_line("Repo-map: disabled") == []
        assert p.parse_event_line("https://aider.chat") == []
        assert p.parse_event_line("Warning: Something") == []
        assert p.parse_event_line("Added .aider* to .gitignore") == []
        assert p.parse_event_line("Git repository created") == []
        assert p.parse_event_line("litellm.RateLimitError: whoops") == []
        assert p.parse_event_line("Did you mean one of these?") == []
        assert p.parse_event_line("You can skip this check") == []

    def test_parse_empty_line(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        assert p.parse_event_line("") == []
        assert p.parse_event_line("   ") == []

    def test_extract_text_filters_headers(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        lines = [
            "Aider v0.86.2",
            "Model: openrouter/test",
            "",
            "Hello world this is the response",
            "It continues here",
            "",
            "Tokens: 100 sent, 50 received.",
        ]
        text = p.extract_text(lines)
        assert "Aider v0.86.2" not in text
        assert "Model:" not in text
        assert "Tokens:" not in text
        assert "Hello world this is the response" in text
        assert "It continues here" in text

    def test_extract_session_id_none(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        assert p.extract_session_id(["any lines"]) is None

    def test_build_env_returns_env(self):
        from agentpipe.providers.aider import AiderProvider

        p = AiderProvider()
        env = p.build_env()
        assert isinstance(env, dict)
        assert "PATH" in env


class TestAiderAgentIntegration:
    def test_aider_agent_creation(self):
        from agentpipe._agent import Agent

        agent = Agent("aider")
        assert agent.provider == "aider"
        assert agent.model == "openrouter/google/gemma-4-26b-a4b-it:free"

    def test_aider_agent_custom_model(self):
        from agentpipe._agent import Agent

        agent = Agent("aider", model="openrouter/qwen/qwen3-coder:free")
        assert agent.model == "openrouter/qwen/qwen3-coder:free"

    def test_aider_agent_files(self):
        from agentpipe._agent import Agent

        agent = Agent("aider", files=["main.py"])
        cmd = agent._provider_instance.build_command("test")
        assert "--file" in cmd
        idx = cmd.index("--file")
        assert cmd[idx + 1] == "main.py"


class TestKiloProviderConstruction:
    def test_default_model(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        assert p.model == "kilo/kilo-auto/free"
        assert p.binary_name == "kilo"

    def test_custom_model(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(model="kilo/~anthropic/claude-sonnet-latest")
        assert p.model == "kilo/~anthropic/claude-sonnet-latest"

    def test_run_command(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        cmd = p.build_command("hello")
        assert cmd[0] == "kilo"
        assert cmd[1] == "run"
        assert cmd[2] == "hello"

    def test_json_format(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        cmd = p.build_command("test")
        assert "--format=json" in cmd

    def test_model_flag(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        cmd = p.build_command("test")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "kilo/kilo-auto/free"

    def test_auto_flag_for_non_yolo_approval(self):
        from agentpipe._types import ApprovalMode
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(approval_mode=ApprovalMode.PLAN)
        cmd = p.build_command("test")
        assert "--auto" in cmd
        assert "--dangerously-skip-permissions" not in cmd

    def test_dangerously_skip_permissions_for_yolo(self):
        from agentpipe._types import ApprovalMode
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(approval_mode=ApprovalMode.YOLO)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd
        assert "--auto" not in cmd

    def test_default_uses_skip_permissions(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_continue_flag(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(continue_last=True)
        cmd = p.build_command("test")
        assert "--continue" in cmd

    def test_session_flag(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        cmd = p.build_command("test", session_id="ses_abc")
        assert "--session" in cmd
        idx = cmd.index("--session")
        assert cmd[idx + 1] == "ses_abc"

    def test_fork_flag(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(fork_session=True)
        cmd = p.build_command("test")
        assert "--fork" in cmd

    def test_agent_flag(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(agent_name="architect")
        cmd = p.build_command("test")
        assert "--agent" in cmd
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "architect"

    def test_title_flag(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(session_name="my-session")
        cmd = p.build_command("test")
        assert "--title" in cmd
        idx = cmd.index("--title")
        assert cmd[idx + 1] == "my-session"

    def test_files_flag(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(files=["main.py", "utils.py"])
        cmd = p.build_command("test")
        assert cmd.count("--file") == 2
        idx1 = cmd.index("--file")
        assert cmd[idx1 + 1] == "main.py"

    def test_dir_flag(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(include_dirs=["/src"])
        cmd = p.build_command("test")
        assert "--dir" in cmd
        idx = cmd.index("--dir")
        assert cmd[idx + 1] == "/src"

    def test_variant_flag(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(effort="high")
        cmd = p.build_command("test")
        assert "--variant" in cmd
        idx = cmd.index("--variant")
        assert cmd[idx + 1] == "high"

    def test_variant_maps_effort_levels(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(effort="low")
        cmd = p.build_command("test")
        idx = cmd.index("--variant")
        assert cmd[idx + 1] == "minimal"

        p = KiloProvider(effort="medium")
        cmd = p.build_command("test")
        idx = cmd.index("--variant")
        assert cmd[idx + 1] == "low"

        p = KiloProvider(effort="xhigh")
        cmd = p.build_command("test")
        idx = cmd.index("--variant")
        assert cmd[idx + 1] == "max"

        p = KiloProvider(effort="max")
        cmd = p.build_command("test")
        idx = cmd.index("--variant")
        assert cmd[idx + 1] == "max"

    def test_thinking_flag(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(show_thinking=True)
        cmd = p.build_command("test")
        assert "--thinking" in cmd

    def test_no_thinking_default(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        cmd = p.build_command("test")
        assert "--thinking" not in cmd

    def test_sandbox_flag(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_parse_text_event(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        events = p.parse_event_line('{"type":"text","part":{"text":"Hello"}}')
        assert len(events) == 1
        assert events[0].text == "Hello"

    def test_parse_non_json_as_thinking(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        events = p.parse_event_line("Plain text output")
        assert len(events) == 1
        assert events[0].text == "Plain text output"

    def test_parse_empty_line(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        assert p.parse_event_line("") == []
        assert p.parse_event_line("   ") == []

    def test_parse_step_finish_usage(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        line = '{"type":"step_finish","part":{"cost":0.01,"tokens":{"input":100,"output":50,"cache":{"read":10,"write":5}}}}'
        events = p.parse_event_line(line)
        assert len(events) == 1
        assert events[0].input_tokens == 115
        assert events[0].output_tokens == 50
        assert events[0].cost_usd == 0.01
        assert events[0].cache_read_tokens == 10
        assert events[0].cache_write_tokens == 5

    def test_parse_step_finish_with_reasoning(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        line = '{"type":"step_finish","part":{"tokens":{"input":200,"output":30,"reasoning":20}}}'
        events = p.parse_event_line(line)
        assert len(events) == 1
        assert events[0].output_tokens == 50

    def test_parse_tool_use_call(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        line = '{"type":"tool_use","state":{"status":"running","input":{"file":"test.py"}},"part":{"tool":"Read"}}'
        events = p.parse_event_line(line)
        assert len(events) == 1
        assert events[0].tool == "Read"
        assert events[0].args == {"file": "test.py"}

    def test_parse_tool_use_result(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        line = '{"type":"tool_use","state":{"status":"success","input":{"file":"test.py"},"output":"file content"}}'
        events = p.parse_event_line(line)
        assert len(events) == 1
        assert events[0].tool == ""

    def test_extract_session_id(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        lines = [
            '{"type":"text","part":{"text":"Hello"}}',
            '{"type":"step_finish","sessionID":"ses_abc123"}',
        ]
        sid = p.extract_session_id(lines)
        assert sid == "ses_abc123"

    def test_extract_session_id_none(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        assert p.extract_session_id(["no session ID"]) is None

    def test_extract_text(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        lines = [
            '{"type":"text","part":{"text":"Hello "}}',
            '{"type":"text","part":{"text":"world"}}',
            '{"type":"step_finish","part":{"cost":0.01}}',
        ]
        text = p.extract_text(lines)
        assert text == "Hello world"

    def test_build_env(self):
        from agentpipe.providers.kilo import KiloProvider

        p = KiloProvider()
        env = p.build_env()
        assert isinstance(env, dict)
        assert "PATH" in env


class TestKiloAgentIntegration:
    def test_kilo_agent_creation(self):
        from agentpipe._agent import Agent

        agent = Agent("kilo")
        assert agent.provider == "kilo"
        assert agent.model == "kilo/kilo-auto/free"

    def test_kilo_agent_custom_model(self):
        from agentpipe._agent import Agent

        agent = Agent("kilo", model="kilo/~anthropic/claude-sonnet-latest")
        assert agent.model == "kilo/~anthropic/claude-sonnet-latest"

    def test_kilo_agent_approval_mode(self):
        from agentpipe._agent import Agent
        from agentpipe._types import ApprovalMode

        agent = Agent("kilo", approval_mode=ApprovalMode.PLAN)
        cmd = agent._provider_instance.build_command("test")
        assert "--auto" in cmd

    def test_kilo_agent_files(self):
        from agentpipe._agent import Agent

        agent = Agent("kilo", files=["main.py"])
        cmd = agent._provider_instance.build_command("test")
        assert "--file" in cmd
        idx = cmd.index("--file")
        assert cmd[idx + 1] == "main.py"
