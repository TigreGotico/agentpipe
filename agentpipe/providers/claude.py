from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from .._types import (
    AgentEvent,
    ApprovalMode,
    HttpMcpServer,
    McpServerConfig,
    StdioMcpServer,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    UsageEvent,
)


@dataclass
class _ClaudeParsedEvent:
    pass


@dataclass
class _SystemEvent(_ClaudeParsedEvent):
    session_id: str | None = None


@dataclass
class _TextEvent(_ClaudeParsedEvent):
    text: str = ""


@dataclass
class _ToolUseEvent(_ClaudeParsedEvent):
    tool_name: str = ""
    tool_id: str | None = None
    parameters: Any = None


@dataclass
class _ToolResultInternalEvent(_ClaudeParsedEvent):
    output: str = ""
    tool_id: str | None = None


@dataclass
class _MultiEvent(_ClaudeParsedEvent):
    events: list[_ClaudeParsedEvent] = field(default_factory=list)
    usage: dict[str, Any] | None = None


@dataclass
class _ResultInternalEvent(_ClaudeParsedEvent):
    result: str = ""
    num_turns: int | None = None
    usage: dict[str, Any] | None = None
    total_cost_usd: float | None = None
    duration_ms: int | None = None


def _parse_claude_line(line: str) -> _ClaudeParsedEvent | None:
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    event_type = data.get("type")

    if event_type == "system":
        return _SystemEvent(session_id=data.get("session_id"))

    if event_type == "assistant":
        message = data.get("message", {})
        content_blocks = message.get("content", [])
        events: list[_ClaudeParsedEvent] = []
        for block in content_blocks:
            block_type = block.get("type")
            if block_type == "text":
                events.append(_TextEvent(text=block.get("text", "")))
            elif block_type == "tool_use":
                events.append(
                    _ToolUseEvent(
                        tool_name=block.get("name", ""),
                        tool_id=block.get("id"),
                        parameters=block.get("input"),
                    )
                )
        usage = message.get("usage")
        return _MultiEvent(events=events, usage=usage) if events else None

    if event_type == "user":
        message = data.get("message", {})
        content_blocks = message.get("content", [])
        for block in content_blocks:
            if block.get("type") == "tool_result":
                output = block.get("content", "")
                if isinstance(output, list):
                    output = "\n".join(str(item) for item in output)
                return _ToolResultInternalEvent(
                    output=str(output) if output else "",
                    tool_id=block.get("tool_use_id"),
                )
        return None

    if event_type == "result":
        return _ResultInternalEvent(
            result=data.get("result", ""),
            num_turns=data.get("num_turns"),
            usage=data.get("usage"),
            total_cost_usd=data.get("total_cost_usd"),
            duration_ms=data.get("duration_ms"),
        )

    return None


_APPROVAL_MODE_MAP: dict[ApprovalMode, str] = {
    ApprovalMode.DEFAULT: "default",
    ApprovalMode.AUTO_EDIT: "acceptEdits",
    ApprovalMode.YOLO: "bypassPermissions",
    ApprovalMode.PLAN: "plan",
    ApprovalMode.BYPASS: "bypassPermissions",
}


class ClaudeProvider:
    def __init__(
        self,
        model: str | None = None,
        *,
        mcp_servers: list[McpServerConfig] | None = None,
        approval_mode: ApprovalMode | None = None,
        max_budget_usd: float | None = None,
    ) -> None:
        self._model = model
        self._mcp_servers = mcp_servers or []
        self._approval_mode = approval_mode
        self._max_budget_usd = max_budget_usd
        self._tool_map: dict[str, str] = {}
        self._tool_start_times: dict[str, float] = {}

    @property
    def binary_name(self) -> str:
        return "claude"

    @property
    def model(self) -> str | None:
        return self._model

    def _build_mcp_config_json(self) -> str:
        servers: dict[str, dict[str, Any]] = {}
        for server in self._mcp_servers:
            if isinstance(server, HttpMcpServer):
                entry: dict[str, Any] = {"type": "sse", "url": server.url}
                if server.headers:
                    entry["headers"] = dict(server.headers)
                servers[server.name] = entry
            else:
                stdio_entry: dict[str, Any] = {"command": server.command, "args": server.args}
                if isinstance(server, StdioMcpServer) and server.env:
                    stdio_entry["env"] = server.env
                servers[server.name] = stdio_entry
        return json.dumps({"mcpServers": servers})

    def build_command(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        model: str | None = None,
    ) -> list[str]:
        skips_permissions = (
            self._approval_mode is None
            or self._approval_mode == ApprovalMode.BYPASS
            or self._approval_mode == ApprovalMode.YOLO
        )
        permission_flag = "--dangerously-skip-permissions" if skips_permissions else "--permission-mode"
        cmd = [
            self.binary_name,
            "-p",
            permission_flag,
        ]

        if self._approval_mode is not None and self._approval_mode not in (ApprovalMode.BYPASS, ApprovalMode.YOLO):
            cmd.pop()
            cmd.extend(["--permission-mode", _APPROVAL_MODE_MAP[self._approval_mode]])

        cmd.extend(["--output-format", "stream-json", "--verbose"])

        if session_id:
            cmd.extend(["--resume", session_id])

        cmd.append(prompt)

        effective_model = model or self._model
        if effective_model:
            cmd.extend(["--model", effective_model])

        if self._mcp_servers:
            cmd.extend(["--mcp-config", self._build_mcp_config_json(), "--strict-mcp-config"])

        if self._max_budget_usd is not None:
            cmd.extend(["--max-budget-usd", str(self._max_budget_usd)])

        return cmd

    def parse_event_line(self, line: str) -> list[AgentEvent]:
        stripped = line.strip()
        if not stripped:
            return []

        parsed = _parse_claude_line(stripped)
        if parsed is None:
            return [ThinkingEvent(text=stripped)]

        if isinstance(parsed, _MultiEvent):
            events: list[AgentEvent] = []
            for sub in parsed.events:
                events.extend(self._convert_internal_event(sub, time.monotonic()))
            return events

        return self._convert_internal_event(parsed, time.monotonic())

    def _convert_internal_event(self, parsed: _ClaudeParsedEvent, now: float) -> list[AgentEvent]:
        if isinstance(parsed, _TextEvent):
            return [ThinkingEvent(text=parsed.text)]

        if isinstance(parsed, _ToolUseEvent):
            if parsed.tool_id:
                self._tool_map[parsed.tool_id] = parsed.tool_name
                self._tool_start_times[parsed.tool_id] = now
            return [
                ToolCallEvent(
                    tool=parsed.tool_name,
                    args=parsed.parameters,
                    tool_id=parsed.tool_id,
                )
            ]

        if isinstance(parsed, _ToolResultInternalEvent):
            tool_name = self._tool_map.get(parsed.tool_id or "", "Tool")
            start = self._tool_start_times.get(parsed.tool_id or "")
            duration_ms = ((now - start) * 1000) if start else None
            return [
                ToolResultEvent(
                    tool=tool_name,
                    output=parsed.output,
                    duration_ms=duration_ms,
                )
            ]

        if isinstance(parsed, _ResultInternalEvent):
            usage = parsed.usage or {}
            cached = int(usage.get("cache_creation_input_tokens") or 0) + int(usage.get("cache_read_input_tokens") or 0)
            return [
                UsageEvent(
                    input_tokens=int(usage.get("input_tokens") or 0) + cached,
                    output_tokens=int(usage.get("output_tokens") or 0),
                    cost_usd=parsed.total_cost_usd,
                    cache_read_tokens=int(usage.get("cache_read_input_tokens") or 0),
                    cache_write_tokens=int(usage.get("cache_creation_input_tokens") or 0),
                )
            ]

        if isinstance(parsed, _SystemEvent):
            return []

        return []

    def extract_session_id(self, raw_lines: list[str]) -> str | None:
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            parsed = _parse_claude_line(stripped)
            if isinstance(parsed, _SystemEvent) and parsed.session_id:
                return parsed.session_id
        return None

    def extract_text(self, raw_lines: list[str]) -> str:
        text_parts: list[str] = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            parsed = _parse_claude_line(stripped)
            if isinstance(parsed, _TextEvent):
                text_parts.append(parsed.text)
            elif isinstance(parsed, _ResultInternalEvent) and parsed.result:
                return parsed.result
        return "".join(text_parts).strip()

    def build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.setdefault("CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR", "1")
        return env
