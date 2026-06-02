"""Tests for VibeProvider — build_command, parse_event_line, extract_*."""

from __future__ import annotations

import json

from agentpipe._types import ApprovalMode, ThinkingEvent, ToolCallEvent, ToolResultEvent, UsageEvent
from agentpipe.providers.vibe import VibeProvider, _parse_vibe_line


class TestParseVibeLine:
    def test_text_event(self):
        parsed = _parse_vibe_line(json.dumps({"type": "text", "content": "hello"}))
        assert parsed.text == "hello"

    def test_text_event_text_key(self):
        parsed = _parse_vibe_line(json.dumps({"type": "text", "text": "world"}))
        assert parsed.text == "world"

    def test_tool_use_event(self):
        parsed = _parse_vibe_line(
            json.dumps({"type": "tool_use", "name": "Read", "id": "t1", "input": {"path": "a.py"}})
        )
        assert parsed.tool_name == "Read"
        assert parsed.tool_id == "t1"

    def test_tool_use_alt_keys(self):
        parsed = _parse_vibe_line(
            json.dumps({"type": "tool_use", "tool_name": "Write", "tool_id": "t2", "parameters": {}})
        )
        assert parsed.tool_name == "Write"
        assert parsed.tool_id == "t2"

    def test_tool_result_event(self):
        parsed = _parse_vibe_line(json.dumps({"type": "tool_result", "output": "content", "tool_use_id": "t1"}))
        assert parsed.output == "content"
        assert parsed.tool_id == "t1"

    def test_tool_result_list_output(self):
        parsed = _parse_vibe_line(json.dumps({"type": "tool_result", "output": ["a", "b"]}))
        assert "a" in parsed.output
        assert "b" in parsed.output

    def test_usage_event(self):
        parsed = _parse_vibe_line(
            json.dumps({"type": "usage", "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.01})
        )
        assert parsed.input_tokens == 100
        assert parsed.output_tokens == 50
        assert parsed.cost_usd == 0.01

    def test_usage_alt_keys(self):
        parsed = _parse_vibe_line(json.dumps({"type": "usage", "prompt_tokens": 200, "completion_tokens": 80}))
        assert parsed.input_tokens == 200
        assert parsed.output_tokens == 80

    def test_usage_invalid_cost_ignored(self):
        parsed = _parse_vibe_line(json.dumps({"type": "usage", "input_tokens": 1, "cost_usd": "not a number"}))
        assert parsed.cost_usd is None

    def test_unknown_type(self):
        assert _parse_vibe_line(json.dumps({"type": "unknown"})) is None

    def test_invalid_json(self):
        assert _parse_vibe_line("not json") is None


class TestVibeBuildCommand:
    def test_basic_command(self):
        p = VibeProvider()
        cmd = p.build_command("my prompt")
        assert cmd[0] == "vibe"
        assert "--prompt" in cmd
        idx = cmd.index("--prompt")
        assert cmd[idx + 1] == "my prompt"
        assert "--output" in cmd

    def test_approval_mode(self):
        p = VibeProvider(approval_mode=ApprovalMode.YOLO)
        cmd = p.build_command("test")
        assert "--agent" in cmd
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "auto-approve"

    def test_model(self):
        p = VibeProvider(model="custom-model")
        cmd = p.build_command("test")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "custom-model"

    def test_model_override(self):
        p = VibeProvider(model="default")
        cmd = p.build_command("test", model="override")
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "override"

    def test_sandbox(self):
        p = VibeProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_include_dirs(self):
        p = VibeProvider(include_dirs=["/a", "/b"])
        cmd = p.build_command("test")
        assert cmd.count("--add-dir") == 2

    def test_allowed_tools(self):
        p = VibeProvider(allowed_tools=["Read"])
        cmd = p.build_command("test")
        assert "--enabled-tools" in cmd

    def test_session_name_as_workdir(self):
        p = VibeProvider(session_name="my-dir")
        cmd = p.build_command("test")
        assert "--workdir" in cmd
        idx = cmd.index("--workdir")
        assert cmd[idx + 1] == "my-dir"

    def test_continue_last(self):
        p = VibeProvider(continue_last=True)
        cmd = p.build_command("test")
        assert "--continue" in cmd

    def test_resume_session(self):
        p = VibeProvider()
        cmd = p.build_command("test", session_id="v-1")
        assert "--resume" in cmd
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "v-1"

    def test_max_turns(self):
        p = VibeProvider(max_turns=3)
        cmd = p.build_command("test")
        assert "--max-turns" in cmd
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "3"

    def test_max_price(self):
        p = VibeProvider(max_price=1.5)
        cmd = p.build_command("test")
        assert "--max-price" in cmd

    def test_max_tokens(self):
        p = VibeProvider(max_tokens=4096)
        cmd = p.build_command("test")
        assert "--max-tokens" in cmd
        idx = cmd.index("--max-tokens")
        assert cmd[idx + 1] == "4096"

    def test_streaming_output(self):
        p = VibeProvider()
        cmd = p.build_command("test")
        assert "--output" in cmd
        idx = cmd.index("--output")
        assert cmd[idx + 1] == "streaming"

    def test_default_model(self):
        p = VibeProvider()
        assert p.model == "mistral-large-latest"


class TestVibeParseEventLine:
    def test_text_event(self):
        p = VibeProvider()
        events = p.parse_event_line(json.dumps({"type": "text", "content": "hello"}))
        assert isinstance(events[0], ThinkingEvent)
        assert events[0].text == "hello"

    def test_tool_use_event(self):
        p = VibeProvider()
        events = p.parse_event_line(
            json.dumps({"type": "tool_use", "name": "Read", "id": "t1", "input": {"path": "a.py"}})
        )
        assert isinstance(events[0], ToolCallEvent)
        assert events[0].tool == "Read"
        assert events[0].tool_id == "t1"

    def test_tool_result_event(self):
        p = VibeProvider()
        p._tool_map["t1"] = "Read"
        events = p.parse_event_line(json.dumps({"type": "tool_result", "output": "data", "tool_use_id": "t1"}))
        assert isinstance(events[0], ToolResultEvent)
        assert events[0].tool == "Read"

    def test_usage_event(self):
        p = VibeProvider()
        events = p.parse_event_line(
            json.dumps({"type": "usage", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.001})
        )
        assert isinstance(events[0], UsageEvent)
        assert events[0].input_tokens == 10

    def test_invalid_json_returns_thinking(self):
        p = VibeProvider()
        events = p.parse_event_line("plain text")
        assert isinstance(events[0], ThinkingEvent)

    def test_empty_line(self):
        p = VibeProvider()
        assert p.parse_event_line("") == []

    def test_unknown_parsed_type_returns_thinking(self):
        p = VibeProvider()
        events = p.parse_event_line(json.dumps({"type": "foo"}))
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)


class TestVibeExtractSessionId:
    def test_extracts_session_id(self):
        p = VibeProvider()
        lines = [json.dumps({"session_id": "vibe-s1"}) + "\n"]
        assert p.extract_session_id(lines) == "vibe-s1"

    def test_extracts_sessionID(self):
        p = VibeProvider()
        lines = [json.dumps({"sessionID": "vibe-s2"}) + "\n"]
        assert p.extract_session_id(lines) == "vibe-s2"

    def test_no_session_id(self):
        p = VibeProvider()
        lines = [json.dumps({"type": "text"}) + "\n"]
        assert p.extract_session_id(lines) is None

    def test_skips_invalid(self):
        p = VibeProvider()
        lines = ["invalid\n", json.dumps({"session_id": "s3"}) + "\n"]
        assert p.extract_session_id(lines) == "s3"


class TestVibeExtractText:
    def test_extracts_text(self):
        p = VibeProvider()
        lines = [
            json.dumps({"type": "text", "content": "hello "}) + "\n",
            json.dumps({"type": "text", "content": "world"}) + "\n",
        ]
        assert p.extract_text(lines) == "hello world"

    def test_ignores_non_text(self):
        p = VibeProvider()
        lines = [
            json.dumps({"type": "tool_use", "name": "X"}) + "\n",
            json.dumps({"type": "text", "content": "ok"}) + "\n",
        ]
        assert p.extract_text(lines) == "ok"


class TestVibeBuildEnv:
    def test_returns_environ(self):
        p = VibeProvider()
        env = p.build_env()
        assert isinstance(env, dict)
