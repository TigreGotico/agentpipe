from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Any

from .._types import (
    AgentEvent,
    ApprovalMode,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
)

_GeminiParsedEvent = "_GeminiInitEvent | _GeminiMessageEvent | _GeminiToolUseEvent | _GeminiToolResultEvent | None"

_GEMINI_APPROVAL_MAP: dict[ApprovalMode, str] = {
    ApprovalMode.DEFAULT: "default",
    ApprovalMode.AUTO_EDIT: "auto_edit",
    ApprovalMode.YOLO: "yolo",
    ApprovalMode.PLAN: "plan",
    ApprovalMode.BYPASS: "yolo",
}


@dataclass
class _GeminiInitEvent:
    session_id: str | None = None


@dataclass
class _GeminiMessageEvent:
    role: str = ""
    content: str = ""


@dataclass
class _GeminiToolUseEvent:
    tool_name: str = ""
    tool_id: str | None = None
    parameters: Any = None


@dataclass
class _GeminiToolResultEvent:
    output: str = ""
    tool_id: str | None = None


def _parse_gemini_line(
    line: str,
) -> _GeminiInitEvent | _GeminiMessageEvent | _GeminiToolUseEvent | _GeminiToolResultEvent | None:
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    msg_type = data.get("type")

    if msg_type == "init":
        return _GeminiInitEvent(session_id=data.get("session_id"))
    if msg_type == "message":
        return _GeminiMessageEvent(role=data.get("role", ""), content=data.get("content", ""))
    if msg_type == "tool_use":
        return _GeminiToolUseEvent(
            tool_name=data.get("tool_name", ""),
            tool_id=data.get("tool_id"),
            parameters=data.get("parameters"),
        )
    if msg_type == "tool_result":
        return _GeminiToolResultEvent(output=data.get("output", ""), tool_id=data.get("tool_id"))
    return None


class GeminiProvider:
    def __init__(
        self,
        model: str | None = None,
        *,
        sandbox: bool = False,
        include_dirs: list[str] | None = None,
        approval_mode: ApprovalMode | None = None,
        allowed_tools: list[str] | None = None,
        raw_output: bool = False,
        extensions: list[str] | None = None,
        # Accepted but not used by Gemini CLI — forwarded by Agent
        mcp_servers: list | None = None,
        max_budget_usd: float | None = None,
        system_prompt: str | None = None,
        append_system_prompt: str | None = None,
        disallowed_tools: list[str] | None = None,
        effort: str | None = None,
        fallback_model: str | None = None,
        json_schema: dict | None = None,
        agent_name: str | None = None,
        session_name: str | None = None,
        continue_last: bool = False,
        fork_session: bool = False,
        files: list[str] | None = None,
    ) -> None:
        self._model = model
        self._sandbox = sandbox
        self._include_dirs = include_dirs
        self._approval_mode = approval_mode
        self._allowed_tools = allowed_tools
        self._raw_output = raw_output
        self._extensions = extensions
        self._tool_map: dict[str, str] = {}
        self._tool_start_times: dict[str, float] = {}
        self._tool_lock: threading.Lock = threading.Lock()
        self._assistant_turns: int = 0

    @property
    def binary_name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str | None:
        return self._model

    def build_command(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        model: str | None = None,
    ) -> list[str]:
        cmd = [self.binary_name]
        if self._approval_mode == ApprovalMode.YOLO or self._approval_mode == ApprovalMode.BYPASS:
            cmd.append("--yolo")
        elif self._approval_mode is not None and self._approval_mode != ApprovalMode.DEFAULT:
            cmd.extend(["--approval-mode", _GEMINI_APPROVAL_MAP[self._approval_mode]])
        elif self._approval_mode == ApprovalMode.DEFAULT:
            cmd.extend(["--approval-mode", "default"])
        effective_model = model or self._model
        if effective_model:
            cmd.extend(["--model", effective_model])
        if self._sandbox:
            cmd.append("--sandbox")
        if self._include_dirs:
            for d in self._include_dirs:
                cmd.extend(["--include-directories", d])
        if self._allowed_tools:
            for tool in self._allowed_tools:
                cmd.extend(["--allowed-tools", tool])
        if self._extensions:
            for ext in self._extensions:
                cmd.extend(["--extensions", ext])
        if self._raw_output:
            cmd.extend(["--output-format", "json", "--raw-output"])
        else:
            cmd.extend(["--output-format", "stream-json"])
        cmd.extend(["-p", prompt])
        if session_id:
            cmd.extend(["--resume", session_id])
        return cmd

    def parse_event_line(self, line: str) -> list[AgentEvent]:
        stripped = line.strip()
        if not stripped:
            return []

        import time

        parsed = _parse_gemini_line(stripped)
        if parsed is None:
            return [ThinkingEvent(text=stripped)]

        if isinstance(parsed, _GeminiMessageEvent):
            if parsed.role == "assistant":
                self._assistant_turns += 1
                return [ThinkingEvent(text=parsed.content)]
            return []

        if isinstance(parsed, _GeminiToolUseEvent):
            if parsed.tool_id:
                with self._tool_lock:
                    self._tool_map[parsed.tool_id] = parsed.tool_name
                    self._tool_start_times[parsed.tool_id] = time.monotonic()
            return [
                ToolCallEvent(
                    tool=parsed.tool_name,
                    args=parsed.parameters,
                    tool_id=parsed.tool_id,
                )
            ]

        if isinstance(parsed, _GeminiToolResultEvent):
            with self._tool_lock:
                tool_name = self._tool_map.get(parsed.tool_id or "", "Tool")
                start = self._tool_start_times.get(parsed.tool_id or "")
            duration_ms = ((time.monotonic() - start) * 1000) if start else None
            return [
                ToolResultEvent(
                    tool=tool_name,
                    output=parsed.output,
                    duration_ms=duration_ms,
                )
            ]

        return []

    def extract_session_id(self, raw_lines: list[str]) -> str | None:
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            parsed = _parse_gemini_line(stripped)
            if isinstance(parsed, _GeminiInitEvent) and parsed.session_id:
                return parsed.session_id
        return None

    def extract_text(self, raw_lines: list[str]) -> str:
        text_parts: list[str] = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            parsed = _parse_gemini_line(stripped)
            if isinstance(parsed, _GeminiMessageEvent) and parsed.role == "assistant":
                text_parts.append(parsed.content)
        return "".join(text_parts).strip()

    def build_env(self) -> dict[str, str]:
        import os

        env = dict(os.environ)
        env.setdefault("GEMINI_CLI_TRUST_WORKSPACE", "true")
        return env


class GeminiFlashProvider(GeminiProvider):
    """Gemini 2.5 Flash — fast, free-tier model."""

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(model=model or "gemini-2.5-flash", **kwargs)


class GeminiProProvider(GeminiProvider):
    """Gemini 2.5 Pro — premium reasoning model."""

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(model=model or "gemini-2.5-pro", **kwargs)
