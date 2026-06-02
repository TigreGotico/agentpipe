"""Tests for GeminiProvider — build_command, parse_event_line, extract_*."""

from __future__ import annotations

import json

from agentpipe._types import ApprovalMode, ThinkingEvent, ToolCallEvent, ToolResultEvent
from agentpipe.providers.gemini import (
    GeminiFlashProvider,
    GeminiProProvider,
    GeminiProvider,
    _parse_gemini_line,
)


class TestParseGeminiLine:
    def test_init_event(self):
        parsed = _parse_gemini_line(json.dumps({"type": "init", "session_id": "gem-1"}))
        assert parsed.session_id == "gem-1"

    def test_message_event(self):
        parsed = _parse_gemini_line(json.dumps({"type": "message", "role": "assistant", "content": "hi"}))
        assert parsed.role == "assistant"
        assert parsed.content == "hi"

    def test_tool_use_event(self):
        parsed = _parse_gemini_line(
            json.dumps({"type": "tool_use", "tool_name": "Read", "tool_id": "t1", "parameters": {"path": "a.py"}})
        )
        assert parsed.tool_name == "Read"
        assert parsed.tool_id == "t1"

    def test_tool_result_event(self):
        parsed = _parse_gemini_line(json.dumps({"type": "tool_result", "output": "content", "tool_id": "t1"}))
        assert parsed.output == "content"

    def test_unknown_type_returns_none(self):
        assert _parse_gemini_line(json.dumps({"type": "unknown"})) is None

    def test_invalid_json(self):
        assert _parse_gemini_line("not json") is None


class TestGeminiBuildCommand:
    def test_yolo_mode(self):
        p = GeminiProvider(approval_mode=ApprovalMode.YOLO)
        cmd = p.build_command("test")
        assert "--yolo" in cmd

    def test_bypass_mode(self):
        p = GeminiProvider(approval_mode=ApprovalMode.BYPASS)
        cmd = p.build_command("test")
        assert "--yolo" in cmd

    def test_auto_edit_mode(self):
        p = GeminiProvider(approval_mode=ApprovalMode.AUTO_EDIT)
        cmd = p.build_command("test")
        assert "--approval-mode" in cmd
        idx = cmd.index("--approval-mode")
        assert cmd[idx + 1] == "auto_edit"

    def test_default_mode_explicit(self):
        p = GeminiProvider(approval_mode=ApprovalMode.DEFAULT)
        cmd = p.build_command("test")
        assert "--approval-mode" in cmd
        idx = cmd.index("--approval-mode")
        assert cmd[idx + 1] == "default"

    def test_model_flag(self):
        p = GeminiProvider(model="gemini-2.5-pro")
        cmd = p.build_command("test")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "gemini-2.5-pro"

    def test_model_override(self):
        p = GeminiProvider(model="gemini-2.5-flash")
        cmd = p.build_command("test", model="gemini-2.5-pro")
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "gemini-2.5-pro"

    def test_sandbox(self):
        p = GeminiProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_include_dirs(self):
        p = GeminiProvider(include_dirs=["/src", "/lib"])
        cmd = p.build_command("test")
        assert cmd.count("--include-directories") == 2

    def test_allowed_tools(self):
        p = GeminiProvider(allowed_tools=["Read", "Write"])
        cmd = p.build_command("test")
        assert cmd.count("--allowed-tools") == 2

    def test_extensions(self):
        p = GeminiProvider(extensions=["ext-a", "ext-b"])
        cmd = p.build_command("test")
        assert cmd.count("--extensions") == 2

    def test_raw_output(self):
        p = GeminiProvider(raw_output=True)
        cmd = p.build_command("test")
        assert "--raw-output" in cmd
        assert "--output-format" in cmd

    def test_default_stream_json(self):
        p = GeminiProvider()
        cmd = p.build_command("test")
        idx = cmd.index("--output-format")
        assert cmd[idx + 1] == "stream-json"

    def test_prompt_in_command(self):
        p = GeminiProvider()
        cmd = p.build_command("my prompt")
        assert "-p" in cmd
        idx = cmd.index("-p")
        assert cmd[idx + 1] == "my prompt"

    def test_resume_session(self):
        p = GeminiProvider()
        cmd = p.build_command("test", session_id="gem-123")
        assert "--resume" in cmd
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "gem-123"


class TestGeminiParseEventLine:
    def test_assistant_message(self):
        p = GeminiProvider()
        events = p.parse_event_line(json.dumps({"type": "message", "role": "assistant", "content": "hello"}))
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)
        assert events[0].text == "hello"

    def test_user_message_ignored(self):
        p = GeminiProvider()
        events = p.parse_event_line(json.dumps({"type": "message", "role": "user", "content": "q"}))
        assert events == []

    def test_tool_use_event(self):
        p = GeminiProvider()
        events = p.parse_event_line(
            json.dumps({"type": "tool_use", "tool_name": "Write", "tool_id": "t1", "parameters": {}})
        )
        assert len(events) == 1
        assert isinstance(events[0], ToolCallEvent)
        assert events[0].tool == "Write"

    def test_tool_result_event(self):
        p = GeminiProvider()
        p._tools._map["t1"] = "Read"
        events = p.parse_event_line(json.dumps({"type": "tool_result", "output": "data", "tool_id": "t1"}))
        assert isinstance(events[0], ToolResultEvent)
        assert events[0].tool == "Read"

    def test_init_event_returns_empty(self):
        p = GeminiProvider()
        events = p.parse_event_line(json.dumps({"type": "init", "session_id": "s"}))
        assert events == []

    def test_invalid_json_returns_thinking(self):
        p = GeminiProvider()
        events = p.parse_event_line("plain text")
        assert isinstance(events[0], ThinkingEvent)

    def test_empty_line(self):
        p = GeminiProvider()
        assert p.parse_event_line("") == []

    def test_assistant_turns_counter(self):
        p = GeminiProvider()
        assert p._assistant_turns == 0
        p.parse_event_line(json.dumps({"type": "message", "role": "assistant", "content": "a"}))
        assert p._assistant_turns == 1
        p.parse_event_line(json.dumps({"type": "message", "role": "assistant", "content": "b"}))
        assert p._assistant_turns == 2


class TestGeminiExtractSessionId:
    def test_extracts_from_init(self):
        p = GeminiProvider()
        lines = [json.dumps({"type": "init", "session_id": "gem-s1"}) + "\n"]
        assert p.extract_session_id(lines) == "gem-s1"

    def test_no_session_id(self):
        p = GeminiProvider()
        lines = [json.dumps({"type": "message", "role": "assistant"}) + "\n"]
        assert p.extract_session_id(lines) is None


class TestGeminiExtractText:
    def test_extracts_assistant_text(self):
        p = GeminiProvider()
        lines = [
            json.dumps({"type": "message", "role": "assistant", "content": "hello "}) + "\n",
            json.dumps({"type": "message", "role": "assistant", "content": "world"}) + "\n",
        ]
        assert p.extract_text(lines) == "hello world"

    def test_ignores_user_text(self):
        p = GeminiProvider()
        lines = [
            json.dumps({"type": "message", "role": "user", "content": "question"}) + "\n",
            json.dumps({"type": "message", "role": "assistant", "content": "answer"}) + "\n",
        ]
        assert p.extract_text(lines) == "answer"


class TestGeminiBuildEnv:
    def test_includes_trust_workspace(self):
        p = GeminiProvider()
        env = p.build_env()
        assert env.get("GEMINI_CLI_TRUST_WORKSPACE") == "true"


class TestGeminiSubclasses:
    def test_flash_default_model(self):
        p = GeminiFlashProvider()
        assert p.model == "gemini-2.5-flash"

    def test_pro_default_model(self):
        p = GeminiProProvider()
        assert p.model == "gemini-2.5-pro"

    def test_flash_custom_model(self):
        p = GeminiFlashProvider(model="custom")
        assert p.model == "custom"
