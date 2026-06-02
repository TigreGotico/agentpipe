"""Tests for QoderProvider — build_command options, parse_event_line, extract_*."""

from __future__ import annotations

import json

from agentpipe._types import (
    ApprovalMode,
    HttpMcpServer,
    StdioMcpServer,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    UsageEvent,
)
from agentpipe.providers.qoder import QoderProvider


class TestQoderBuildCommand:
    def test_default_skips_permissions(self):
        p = QoderProvider()
        cmd = p.build_command("hello")
        assert "--dangerously-skip-permissions" in cmd

    def test_explicit_bypass_skips_permissions(self):
        p = QoderProvider(approval_mode=ApprovalMode.BYPASS)
        cmd = p.build_command("hello")
        assert "--dangerously-skip-permissions" in cmd

    def test_plan_mode_uses_permission_mode(self):
        p = QoderProvider(approval_mode=ApprovalMode.PLAN)
        cmd = p.build_command("hello")
        assert "--permission-mode" in cmd
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "plan"
        assert "--dangerously-skip-permissions" not in cmd

    def test_auto_edit_mode(self):
        p = QoderProvider(approval_mode=ApprovalMode.AUTO_EDIT)
        cmd = p.build_command("hello")
        assert "--permission-mode" in cmd
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "accept_edits"

    def test_system_prompt(self):
        p = QoderProvider(system_prompt="You are a coder")
        cmd = p.build_command("test")
        assert "--system-prompt" in cmd

    def test_append_system_prompt(self):
        p = QoderProvider(append_system_prompt="Be concise")
        cmd = p.build_command("test")
        assert "--append-system-prompt" in cmd

    def test_allowed_tools(self):
        p = QoderProvider(allowed_tools=["Read", "Write"])
        cmd = p.build_command("test")
        assert cmd.count("--allowed-tools") == 2

    def test_disallowed_tools(self):
        p = QoderProvider(disallowed_tools=["Bash"])
        cmd = p.build_command("test")
        assert "--disallowed-tools" in cmd

    def test_effort(self):
        p = QoderProvider(effort="high")
        cmd = p.build_command("test")
        assert "--effort" in cmd
        idx = cmd.index("--effort")
        assert cmd[idx + 1] == "high"

    def test_fallback_model(self):
        p = QoderProvider(fallback_model="backup")
        cmd = p.build_command("test")
        assert "--fallback-model" in cmd

    def test_json_schema(self):
        schema = {"type": "object"}
        p = QoderProvider(json_schema=schema)
        cmd = p.build_command("test")
        assert "--output-format" in cmd
        assert "--json-schema" in cmd

    def test_raw_output(self):
        p = QoderProvider(raw_output=True)
        cmd = p.build_command("test")
        assert "--verbose" not in cmd

    def test_default_has_verbose(self):
        p = QoderProvider()
        cmd = p.build_command("test")
        assert "--verbose" in cmd

    def test_resume_session(self):
        p = QoderProvider()
        cmd = p.build_command("test", session_id="sess-1")
        assert "--resume" in cmd
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "sess-1"

    def test_continue_last(self):
        p = QoderProvider(continue_last=True)
        cmd = p.build_command("test")
        assert "--continue" in cmd

    def test_fork_session(self):
        p = QoderProvider(fork_session=True)
        cmd = p.build_command("test")
        assert "--fork-session" in cmd

    def test_sandbox(self):
        p = QoderProvider(sandbox=True)
        cmd = p.build_command("test")
        assert "--sandbox" in cmd

    def test_agent_name(self):
        p = QoderProvider(agent_name="coder")
        cmd = p.build_command("test")
        assert "--agent" in cmd

    def test_session_name(self):
        p = QoderProvider(session_name="my-sess")
        cmd = p.build_command("test")
        assert "--name" in cmd

    def test_include_dirs(self):
        p = QoderProvider(include_dirs=["/src", "/lib"])
        cmd = p.build_command("test")
        assert cmd.count("--add-dir") == 2

    def test_files(self):
        p = QoderProvider(files=["a.py", "b.py"])
        cmd = p.build_command("test")
        assert cmd.count("--file") == 2

    def test_max_turns(self):
        p = QoderProvider(max_turns=5)
        cmd = p.build_command("test")
        assert "--max-turns" in cmd
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "5"

    def test_model_in_command(self):
        p = QoderProvider(model="my-model")
        cmd = p.build_command("test")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "my-model"

    def test_model_override_in_command(self):
        p = QoderProvider(model="default-model")
        cmd = p.build_command("test", model="override")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "override"

    def test_mcp_servers_config(self):
        http_srv = HttpMcpServer(name="http-srv", url="http://localhost:8080")
        stdio_srv = StdioMcpServer(name="stdio-srv", command="node", args=["server.js"], env={"PORT": "3000"})
        p = QoderProvider(mcp_servers=[http_srv, stdio_srv])
        cmd = p.build_command("test")
        assert "--mcp-config" in cmd
        assert "--strict-mcp-config" in cmd

    def test_max_budget(self):
        p = QoderProvider(max_budget_usd=10.0)
        cmd = p.build_command("test")
        assert "--max-budget-usd" in cmd
        idx = cmd.index("--max-budget-usd")
        assert cmd[idx + 1] == "10.0"


class TestQoderParseEventLine:
    def test_text_event(self):
        p = QoderProvider()
        events = p.parse_event_line(json.dumps({"type": "text", "content": "hello"}))
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)
        assert events[0].text == "hello"

    def test_assistant_event(self):
        p = QoderProvider()
        events = p.parse_event_line(json.dumps({"type": "assistant", "content": "world"}))
        assert isinstance(events[0], ThinkingEvent)

    def test_assistant_content_list(self):
        p = QoderProvider()
        content = [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}, "plain"]
        events = p.parse_event_line(json.dumps({"type": "text", "content": content}))
        assert isinstance(events[0], ThinkingEvent)
        assert events[0].text == "abplain"

    def test_tool_use_event(self):
        p = QoderProvider()
        line = json.dumps({"type": "tool_use", "name": "Read", "id": "t1", "input": {"path": "a.py"}})
        events = p.parse_event_line(line)
        assert len(events) == 1
        assert isinstance(events[0], ToolCallEvent)
        assert events[0].tool == "Read"
        assert events[0].tool_id == "t1"

    def test_tool_result_event(self):
        p = QoderProvider()
        p._tool_map["t1"] = "Read"
        line = json.dumps({"type": "tool_result", "output": "contents", "tool_use_id": "t1"})
        events = p.parse_event_line(line)
        assert len(events) == 1
        assert isinstance(events[0], ToolResultEvent)
        assert events[0].tool == "Read"
        assert events[0].output == "contents"

    def test_tool_result_list_output(self):
        p = QoderProvider()
        line = json.dumps({"type": "tool_result", "output": ["line1", "line2"]})
        events = p.parse_event_line(line)
        assert "line1" in events[0].output

    def test_result_event(self):
        p = QoderProvider()
        line = json.dumps(
            {
                "type": "result",
                "usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 10},
                "total_cost_usd": 0.005,
            }
        )
        events = p.parse_event_line(line)
        assert len(events) == 1
        assert isinstance(events[0], UsageEvent)
        assert events[0].output_tokens == 50
        assert events[0].cost_usd == 0.005

    def test_system_event_returns_empty(self):
        p = QoderProvider()
        events = p.parse_event_line(json.dumps({"type": "system"}))
        assert events == []

    def test_invalid_json_returns_thinking(self):
        p = QoderProvider()
        events = p.parse_event_line("not json")
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)

    def test_empty_line_returns_empty(self):
        p = QoderProvider()
        events = p.parse_event_line("")
        assert events == []

    def test_unknown_type_returns_empty(self):
        p = QoderProvider()
        events = p.parse_event_line(json.dumps({"type": "unknown_type"}))
        assert events == []


class TestQoderExtractSessionId:
    def test_extracts_session_id(self):
        p = QoderProvider()
        lines = ['{"type":"system","session_id":"qoder-sess-1"}\n', '{"type":"result"}\n']
        assert p.extract_session_id(lines) == "qoder-sess-1"

    def test_no_session_id(self):
        p = QoderProvider()
        lines = ['{"type":"result"}\n']
        assert p.extract_session_id(lines) is None

    def test_skips_empty_lines(self):
        p = QoderProvider()
        lines = ["\n", '{"type":"system","session_id":"s1"}\n']
        assert p.extract_session_id(lines) == "s1"

    def test_invalid_json_skipped(self):
        p = QoderProvider()
        lines = ["not json\n", '{"session_id":"s2"}\n']
        assert p.extract_session_id(lines) == "s2"


class TestQoderExtractText:
    def test_extracts_text_from_text_events(self):
        p = QoderProvider()
        lines = [
            json.dumps({"type": "text", "content": "hello "}) + "\n",
            json.dumps({"type": "text", "content": "world"}) + "\n",
        ]
        assert p.extract_text(lines) == "hello world"

    def test_result_event_returns_result(self):
        p = QoderProvider()
        lines = [
            json.dumps({"type": "text", "content": "draft"}) + "\n",
            json.dumps({"type": "result", "result": "final answer"}) + "\n",
        ]
        assert p.extract_text(lines) == "final answer"

    def test_content_list(self):
        p = QoderProvider()
        content = [{"type": "text", "text": "part1"}, {"type": "text", "text": "part2"}]
        lines = [json.dumps({"type": "text", "content": content}) + "\n"]
        text = p.extract_text(lines)
        assert "part1" in text
        assert "part2" in text

    def test_empty_lines_skipped(self):
        p = QoderProvider()
        lines = ["\n", json.dumps({"type": "text", "content": "x"}) + "\n"]
        assert p.extract_text(lines) == "x"

    def test_invalid_json_skipped(self):
        p = QoderProvider()
        lines = ["not json\n", json.dumps({"type": "text", "content": "ok"}) + "\n"]
        assert p.extract_text(lines) == "ok"


class TestQoderBuildEnv:
    def test_returns_environ_copy(self):
        p = QoderProvider()
        env = p.build_env()
        assert isinstance(env, dict)
        assert "PATH" in env
