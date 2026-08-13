"""Tests for MimocodeProvider — build_command, parse_event_line, extract_*."""

from __future__ import annotations

import json

from agentpipe._types import ApprovalMode, ThinkingEvent, ToolCallEvent, ToolResultEvent, UsageEvent
from agentpipe.providers.mimocode import MimocodeProvider, _parse_mimo_line


class TestParseMimoLine:
    def test_text_event(self):
        parsed = _parse_mimo_line(
            json.dumps({"type": "text", "part": {"text": "hello"}})
        )
        assert isinstance(parsed, _parse_mimo_line("not json").__class__) is False
        assert parsed.text == "hello"

    def test_reasoning_event(self):
        parsed = _parse_mimo_line(
            json.dumps({"type": "reasoning", "part": {"text": "thinking..."}})
        )
        assert parsed.text == "thinking..."

    def test_tool_use_event(self):
        parsed = _parse_mimo_line(
            json.dumps({"type": "tool_use", "part": {"name": "Read", "id": "t1", "input": {"path": "a.py"}}})
        )
        assert parsed.tool_name == "Read"
        assert parsed.tool_id == "t1"

    def test_tool_use_alt_keys(self):
        parsed = _parse_mimo_line(
            json.dumps({"type": "tool_use", "part": {"tool_name": "Write", "tool_id": "t2", "parameters": {}}})
        )
        assert parsed.tool_name == "Write"
        assert parsed.tool_id == "t2"

    def test_tool_result_event(self):
        parsed = _parse_mimo_line(
            json.dumps({"type": "tool_result", "part": {"output": "content", "tool_use_id": "t1"}})
        )
        assert parsed.output == "content"
        assert parsed.tool_id == "t1"

    def test_tool_result_list_output(self):
        parsed = _parse_mimo_line(
            json.dumps({"type": "tool_result", "part": {"output": ["a", "b"]}})
        )
        assert "a" in parsed.output
        assert "b" in parsed.output

    def test_step_finish_event(self):
        parsed = _parse_mimo_line(
            json.dumps({
                "type": "step_finish",
                "part": {
                    "tokens": {"input": 100, "output": 50, "reasoning": 10, "cache": {"read": 20, "write": 0}},
                    "cost": 0.001,
                },
            })
        )
        assert parsed.tokens["input"] == 100
        assert parsed.cost == 0.001

    def test_error_event(self):
        parsed = _parse_mimo_line(
            json.dumps({"type": "error", "error": {"name": "APIError", "data": {"message": "bad key"}}})
        )
        assert parsed.message == "bad key"

    def test_unknown_type(self):
        assert _parse_mimo_line(json.dumps({"type": "unknown"})) is None

    def test_invalid_json(self):
        assert _parse_mimo_line("not json") is None


class TestMimocodeBuildCommand:
    def test_basic_command(self):
        p = MimocodeProvider()
        cmd = p.build_command("my prompt")
        assert cmd[0] == "mimo"
        assert "run" in cmd
        assert "--format" in cmd
        idx = cmd.index("--format")
        assert cmd[idx + 1] == "json"
        assert "my prompt" in cmd

    def test_approval_mode_bypass(self):
        p = MimocodeProvider(approval_mode=ApprovalMode.YOLO)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_approval_mode_default(self):
        p = MimocodeProvider(approval_mode=ApprovalMode.DEFAULT)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" not in cmd

    def test_model(self):
        p = MimocodeProvider(model="custom-model")
        cmd = p.build_command("test")
        assert "-m" in cmd
        idx = cmd.index("-m")
        assert cmd[idx + 1] == "custom-model"

    def test_model_override(self):
        p = MimocodeProvider(model="default")
        cmd = p.build_command("test", model="override")
        idx = cmd.index("-m")
        assert cmd[idx + 1] == "override"

    def test_sandbox(self):
        p = MimocodeProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_include_dirs(self):
        p = MimocodeProvider(include_dirs=["/a", "/b"])
        cmd = p.build_command("test")
        assert cmd.count("--dir") == 2

    def test_agent_name(self):
        p = MimocodeProvider(agent_name="my-agent")
        cmd = p.build_command("test")
        assert "--agent" in cmd
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "my-agent"

    def test_session_name(self):
        p = MimocodeProvider(session_name="my-session")
        cmd = p.build_command("test")
        assert "--title" in cmd
        idx = cmd.index("--title")
        assert cmd[idx + 1] == "my-session"

    def test_continue_last(self):
        p = MimocodeProvider(continue_last=True)
        cmd = p.build_command("test")
        assert "-c" in cmd

    def test_resume_session(self):
        p = MimocodeProvider()
        cmd = p.build_command("test", session_id="ses_abc")
        assert "-s" in cmd
        idx = cmd.index("-s")
        assert cmd[idx + 1] == "ses_abc"

    def test_fork_session(self):
        p = MimocodeProvider(fork_session=True)
        cmd = p.build_command("test", session_id="ses_abc")
        assert "--fork" in cmd

    def test_fork_without_session_no_fork_flag(self):
        p = MimocodeProvider(fork_session=True)
        cmd = p.build_command("test")
        assert "--fork" not in cmd

    def test_variant(self):
        p = MimocodeProvider(variant="high")
        cmd = p.build_command("test")
        assert "--variant" in cmd
        idx = cmd.index("--variant")
        assert cmd[idx + 1] == "high"

    def test_thinking(self):
        p = MimocodeProvider(thinking=True)
        cmd = p.build_command("test")
        assert "--thinking" in cmd

    def test_files(self):
        p = MimocodeProvider(files=["a.py", "b.py"])
        cmd = p.build_command("test")
        assert cmd.count("-f") == 2

    def test_default_model(self):
        p = MimocodeProvider()
        assert p.model == "mimo/mimo-auto"


class TestMimocodeParseEventLine:
    def test_text_event(self):
        p = MimocodeProvider()
        events = p.parse_event_line(
            json.dumps({"type": "text", "part": {"text": "hello"}})
        )
        assert isinstance(events[0], ThinkingEvent)
        assert events[0].text == "hello"

    def test_reasoning_event(self):
        p = MimocodeProvider()
        events = p.parse_event_line(
            json.dumps({"type": "reasoning", "part": {"text": "thinking"}})
        )
        assert isinstance(events[0], ThinkingEvent)
        assert events[0].text == "thinking"

    def test_tool_use_event(self):
        p = MimocodeProvider()
        events = p.parse_event_line(
            json.dumps({"type": "tool_use", "part": {"name": "Read", "id": "t1", "input": {"path": "a.py"}}})
        )
        assert isinstance(events[0], ToolCallEvent)
        assert events[0].tool == "Read"
        assert events[0].tool_id == "t1"

    def test_tool_result_event(self):
        p = MimocodeProvider()
        p._tools._map["t1"] = "Read"
        events = p.parse_event_line(
            json.dumps({"type": "tool_result", "part": {"output": "data", "tool_use_id": "t1"}})
        )
        assert isinstance(events[0], ToolResultEvent)
        assert events[0].tool == "Read"

    def test_step_finish_event(self):
        p = MimocodeProvider()
        events = p.parse_event_line(
            json.dumps({
                "type": "step_finish",
                "part": {
                    "tokens": {"input": 10, "output": 5, "reasoning": 2, "cache": {"read": 3, "write": 0}},
                    "cost": 0.001,
                },
            })
        )
        assert isinstance(events[0], UsageEvent)
        assert events[0].input_tokens == 13  # 10 input + 3 cache read + 0 cache write
        assert events[0].output_tokens == 7  # 5 output + 2 reasoning
        assert events[0].cost_usd == 0.001

    def test_error_event(self):
        p = MimocodeProvider()
        events = p.parse_event_line(
            json.dumps({"type": "error", "error": {"data": {"message": "bad key"}}})
        )
        assert isinstance(events[0], ThinkingEvent)
        assert "bad key" in events[0].text

    def test_invalid_json_returns_thinking(self):
        p = MimocodeProvider()
        events = p.parse_event_line("plain text")
        assert isinstance(events[0], ThinkingEvent)

    def test_empty_line(self):
        p = MimocodeProvider()
        assert p.parse_event_line("") == []

    def test_unknown_parsed_type_returns_thinking(self):
        p = MimocodeProvider()
        events = p.parse_event_line(json.dumps({"type": "foo"}))
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)


class TestMimocodeExtractSessionId:
    def test_extracts_session_id(self):
        p = MimocodeProvider()
        lines = [json.dumps({"sessionID": "ses_abc123"}) + "\n"]
        assert p.extract_session_id(lines) == "ses_abc123"

    def test_no_session_id(self):
        p = MimocodeProvider()
        lines = [json.dumps({"type": "text"}) + "\n"]
        assert p.extract_session_id(lines) is None

    def test_skips_invalid(self):
        p = MimocodeProvider()
        lines = ["invalid\n", json.dumps({"sessionID": "ses_xyz"}) + "\n"]
        assert p.extract_session_id(lines) == "ses_xyz"


class TestMimocodeExtractText:
    def test_extracts_text(self):
        p = MimocodeProvider()
        lines = [
            json.dumps({"type": "text", "part": {"text": "hello "}}) + "\n",
            json.dumps({"type": "text", "part": {"text": "world"}}) + "\n",
        ]
        assert p.extract_text(lines) == "hello world"

    def test_ignores_non_text(self):
        p = MimocodeProvider()
        lines = [
            json.dumps({"type": "reasoning", "part": {"text": "thinking"}}) + "\n",
            json.dumps({"type": "text", "part": {"text": "ok"}}) + "\n",
        ]
        assert p.extract_text(lines) == "ok"


class TestMimocodeBuildEnv:
    def test_returns_environ(self):
        p = MimocodeProvider()
        env = p.build_env()
        assert isinstance(env, dict)
