"""Tests for AntigravityProvider — build_command, parse_event_line, extract_*."""

from __future__ import annotations

import os
import tempfile
from agentpipe._types import ApprovalMode, ThinkingEvent
from agentpipe.providers.antigravity import AntigravityProvider


class TestAntigravityBuildCommand:
    def test_basic_command(self):
        p = AntigravityProvider()
        cmd = p.build_command("my prompt")
        assert cmd[0] == "agy"
        assert "--print" in cmd
        idx = cmd.index("--print")
        assert cmd[idx + 1] == "my prompt"
        assert "--dangerously-skip-permissions" in cmd

    def test_approval_mode_default(self):
        p = AntigravityProvider(approval_mode=ApprovalMode.DEFAULT)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" not in cmd

    def test_approval_mode_yolo(self):
        p = AntigravityProvider(approval_mode=ApprovalMode.YOLO)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_model(self):
        p = AntigravityProvider(model="custom-model")
        cmd = p.build_command("test")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "custom-model"

    def test_model_override(self):
        p = AntigravityProvider(model="default")
        cmd = p.build_command("test", model="override")
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "override"

    def test_sandbox(self):
        p = AntigravityProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_include_dirs(self):
        p = AntigravityProvider(include_dirs=["/a", "/b"])
        cmd = p.build_command("test")
        assert cmd.count("--add-dir") == 2
        idx1 = cmd.index("--add-dir")
        assert cmd[idx1 + 1] == "/a"

    def test_continue_last(self):
        p = AntigravityProvider(continue_last=True)
        cmd = p.build_command("test")
        assert "--continue" in cmd

    def test_resume_session(self):
        p = AntigravityProvider()
        cmd = p.build_command("test", session_id="conv-123")
        assert "--conversation" in cmd
        idx = cmd.index("--conversation")
        assert cmd[idx + 1] == "conv-123"

    def test_log_file_generation(self):
        p = AntigravityProvider()
        cmd = p.build_command("test")
        assert "--log-file" in cmd
        idx = cmd.index("--log-file")
        log_path = cmd[idx + 1]
        assert log_path.startswith(tempfile.gettempdir())
        assert os.path.exists(log_path)
        # Clean up
        p.__del__()
        assert not os.path.exists(log_path)


class TestAntigravityParseEventLine:
    def test_thinking_event(self):
        p = AntigravityProvider()
        events = p.parse_event_line("hello world")
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)
        assert events[0].text == "hello world"

    def test_empty_line(self):
        p = AntigravityProvider()
        assert p.parse_event_line("") == []


class TestAntigravityExtractSessionId:
    def test_extracts_session_id_from_log(self):
        p = AntigravityProvider()
        # Build command to initialize temp file path
        p.build_command("test")
        log_path = p._last_log_file
        
        # Write mock log content containing conversation ID
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("I0610 18:29:24.042450 2137301 server.go:753] Created conversation eae4c37d-a139-4793-8fc0-1d0790b5fedf\n")
            
        session_id = p.extract_session_id([])
        assert session_id == "eae4c37d-a139-4793-8fc0-1d0790b5fedf"
        
        p.__del__()

    def test_no_log_file(self):
        p = AntigravityProvider()
        assert p.extract_session_id([]) is None

    def test_no_match_in_log(self):
        p = AntigravityProvider()
        p.build_command("test")
        log_path = p._last_log_file
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("Some unrelated log messages\n")
            
        assert p.extract_session_id([]) is None
        p.__del__()


class TestAntigravityExtractText:
    def test_extracts_text_with_newlines(self):
        p = AntigravityProvider()
        raw = ["Hello!\r\n", "How are you?\n", "", "Fine."]
        assert p.extract_text(raw) == "Hello!\nHow are you?\n\nFine."
