"""Tests for OpencodeProvider — build_command, parse_event_line, extract_*."""

from __future__ import annotations

import json

from agentpipe._types import ApprovalMode, ThinkingEvent, ToolCallEvent, ToolResultEvent, UsageEvent
from agentpipe.providers.opencode import (
    OpencodeFreeProvider,
    OpencodeGoProvider,
    OpencodeProvider,
    OpencodeZenProvider,
    _parse_opencode_line,
)


class TestParseOpencodeLine:
    def test_text_event(self):
        parsed = _parse_opencode_line(json.dumps({"type": "text", "part": {"text": "hello"}}))
        assert parsed.text == "hello"

    def test_tool_use_event(self):
        parsed = _parse_opencode_line(
            json.dumps(
                {
                    "type": "tool_use",
                    "part": {"tool": "Read"},
                    "state": {"input": {"path": "a.py"}, "output": "content", "status": "success"},
                }
            )
        )
        assert parsed.tool_name == "Read"
        assert parsed.status == "success"

    def test_step_start(self):
        parsed = _parse_opencode_line(json.dumps({"type": "step_start", "part": {}}))
        assert parsed is not None

    def test_step_finish(self):
        parsed = _parse_opencode_line(
            json.dumps(
                {
                    "type": "step_finish",
                    "part": {
                        "reason": "done",
                        "cost": 0.01,
                        "tokens": {"input": 100, "output": 50, "cache": {"read": 10, "write": 5}},
                    },
                }
            )
        )
        assert parsed.reason == "done"
        assert parsed.cost == 0.01

    def test_unknown_type(self):
        assert _parse_opencode_line(json.dumps({"type": "unknown"})) is None

    def test_invalid_json(self):
        assert _parse_opencode_line("not json") is None


class TestOpencodeBuildCommand:
    def test_basic_command(self):
        p = OpencodeProvider()
        cmd = p.build_command("hello")
        assert cmd[0] == "opencode"
        assert cmd[1] == "run"
        assert "hello" in cmd
        assert "--format=json" in cmd

    def test_default_skips_permissions(self):
        p = OpencodeProvider()
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_bypass_skips_permissions(self):
        p = OpencodeProvider(approval_mode=ApprovalMode.BYPASS)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_session_id(self):
        p = OpencodeProvider()
        cmd = p.build_command("test", session_id="oc-1")
        assert "--session" in cmd
        idx = cmd.index("--session")
        assert cmd[idx + 1] == "oc-1"

    def test_continue_last(self):
        p = OpencodeProvider(continue_last=True)
        cmd = p.build_command("test")
        assert "--continue" in cmd

    def test_fork_session(self):
        p = OpencodeProvider(fork_session=True)
        cmd = p.build_command("test")
        assert "--fork" in cmd

    def test_sandbox(self):
        p = OpencodeProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_agent_name(self):
        p = OpencodeProvider(agent_name="coder")
        cmd = p.build_command("test")
        assert "--agent" in cmd
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "coder"

    def test_session_name(self):
        p = OpencodeProvider(session_name="my-session")
        cmd = p.build_command("test")
        assert "--title" in cmd
        idx = cmd.index("--title")
        assert cmd[idx + 1] == "my-session"

    def test_model(self):
        p = OpencodeProvider(model="custom-model")
        cmd = p.build_command("test")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "custom-model"

    def test_model_override(self):
        p = OpencodeProvider(model="default")
        cmd = p.build_command("test", model="override")
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "override"

    def test_effort(self):
        p = OpencodeProvider(effort="high")
        cmd = p.build_command("test")
        assert "--variant" in cmd
        idx = cmd.index("--variant")
        assert cmd[idx + 1] == "high"

    def test_effort_mapping(self):
        p = OpencodeProvider(effort="low")
        cmd = p.build_command("test")
        idx = cmd.index("--variant")
        assert cmd[idx + 1] == "minimal"

    def test_include_dirs(self):
        p = OpencodeProvider(include_dirs=["/a", "/b"])
        cmd = p.build_command("test")
        assert cmd.count("--dir") == 2

    def test_files(self):
        p = OpencodeProvider(files=["a.py", "b.py"])
        cmd = p.build_command("test")
        assert cmd.count("--file") == 2


class TestOpencodeParseEventLine:
    def test_text_event(self):
        p = OpencodeProvider()
        events = p.parse_event_line(json.dumps({"type": "text", "part": {"text": "hello"}}))
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)

    def test_tool_use_completed(self):
        p = OpencodeProvider()
        line = json.dumps(
            {
                "type": "tool_use",
                "part": {"tool": "Write"},
                "state": {"input": {"path": "a.py"}, "output": "ok", "status": "success"},
            }
        )
        events = p.parse_event_line(line)
        assert isinstance(events[0], ToolResultEvent)
        assert events[0].tool == "Write"

    def test_tool_use_in_progress(self):
        p = OpencodeProvider()
        line = json.dumps(
            {
                "type": "tool_use",
                "part": {"tool": "Read"},
                "state": {"input": {"path": "x.py"}, "status": "running"},
            }
        )
        events = p.parse_event_line(line)
        assert isinstance(events[0], ToolCallEvent)
        assert events[0].tool == "Read"

    def test_tool_use_dict_args(self):
        p = OpencodeProvider()
        line = json.dumps(
            {
                "type": "tool_use",
                "part": {"tool": "Bash"},
                "state": {"input": {"command": "ls"}, "output": "files", "status": "success"},
            }
        )
        events = p.parse_event_line(line)
        assert isinstance(events[0], ToolResultEvent)

    def test_tool_use_non_dict_args(self):
        p = OpencodeProvider()
        line = json.dumps(
            {
                "type": "tool_use",
                "part": {"tool": "Bash"},
                "state": {"input": "raw string", "output": None, "status": "error"},
            }
        )
        events = p.parse_event_line(line)
        assert isinstance(events[0], ToolResultEvent)

    def test_tool_use_no_input_returns_empty(self):
        p = OpencodeProvider()
        line = json.dumps(
            {
                "type": "tool_use",
                "part": {"tool": "Read"},
                "state": {"status": "pending"},
            }
        )
        events = p.parse_event_line(line)
        assert events == []

    def test_step_finish_event(self):
        p = OpencodeProvider()
        line = json.dumps(
            {
                "type": "step_finish",
                "part": {
                    "cost": 0.01,
                    "tokens": {
                        "input": 100,
                        "output": 50,
                        "reasoning": 10,
                        "cache": {"read": 5, "write": 3},
                    },
                },
            }
        )
        events = p.parse_event_line(line)
        assert isinstance(events[0], UsageEvent)
        assert events[0].input_tokens == 108
        assert events[0].output_tokens == 60
        assert events[0].cost_usd == 0.01
        assert events[0].cache_read_tokens == 5
        assert events[0].cache_write_tokens == 3

    def test_step_start_returns_empty(self):
        p = OpencodeProvider()
        events = p.parse_event_line(json.dumps({"type": "step_start", "part": {}}))
        assert events == []

    def test_invalid_json_returns_thinking(self):
        p = OpencodeProvider()
        events = p.parse_event_line("plain text")
        assert isinstance(events[0], ThinkingEvent)

    def test_empty_line(self):
        p = OpencodeProvider()
        assert p.parse_event_line("") == []


class TestOpencodeExtractSessionId:
    def test_extracts_sessionID(self):
        p = OpencodeProvider()
        lines = [json.dumps({"sessionID": "oc-sess-1"}) + "\n"]
        assert p.extract_session_id(lines) == "oc-sess-1"

    def test_no_session_id(self):
        p = OpencodeProvider()
        lines = [json.dumps({"type": "text"}) + "\n"]
        assert p.extract_session_id(lines) is None

    def test_skips_empty_and_invalid(self):
        p = OpencodeProvider()
        lines = ["\n", "invalid\n", json.dumps({"sessionID": "s2"}) + "\n"]
        assert p.extract_session_id(lines) == "s2"


class TestOpencodeExtractText:
    def test_extracts_text(self):
        p = OpencodeProvider()
        lines = [
            json.dumps({"type": "text", "part": {"text": "hello "}}) + "\n",
            json.dumps({"type": "text", "part": {"text": "world"}}) + "\n",
        ]
        assert p.extract_text(lines) == "hello world"

    def test_ignores_non_text(self):
        p = OpencodeProvider()
        lines = [
            json.dumps({"type": "step_start"}) + "\n",
            json.dumps({"type": "text", "part": {"text": "ok"}}) + "\n",
        ]
        assert p.extract_text(lines) == "ok"


class TestOpencodeBuildEnv:
    def test_returns_environ(self):
        p = OpencodeProvider()
        env = p.build_env()
        assert isinstance(env, dict)


class TestOpencodeSubclasses:
    def test_free_default_model(self):
        p = OpencodeFreeProvider()
        assert p.model == "opencode/big-pickle"
        assert p.plan == "free"

    def test_zen_default_model(self):
        p = OpencodeZenProvider()
        assert p.model == "opencode/gemini-3-flash"
        assert p.plan == "zen"

    def test_go_default_model(self):
        p = OpencodeGoProvider()
        assert p.model == "opencode-go/deepseek-v4-flash"
        assert p.plan == "go"

    def test_custom_model_override(self):
        p = OpencodeFreeProvider(model="custom")
        assert p.model == "custom"
