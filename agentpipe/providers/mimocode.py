from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .._types import (
    AgentEvent,
    ApprovalMode,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from ._utils import ToolTracker, default_build_env, usage_from_step_finish

MIMOCODE_DEFAULT_MODEL = "mimo/mimo-auto"


@dataclass
class _MimoTextEvent:
    text: str = ""


@dataclass
class _MimoReasoningEvent:
    text: str = ""


@dataclass
class _MimoToolUseEvent:
    tool_name: str = ""
    tool_id: str | None = None
    parameters: Any = None


@dataclass
class _MimoToolResultEvent:
    output: str = ""
    tool_id: str | None = None


@dataclass
class _MimoStepFinishEvent:
    tokens: dict[str, Any] | None = None
    cost: float | None = None


@dataclass
class _MimoErrorEvent:
    message: str = ""


def _parse_mimo_line(
    line: str,
) -> (
    _MimoTextEvent
    | _MimoReasoningEvent
    | _MimoToolUseEvent
    | _MimoToolResultEvent
    | _MimoStepFinishEvent
    | _MimoErrorEvent
    | None
):
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    msg_type = data.get("type")
    part = data.get("part", {})

    if msg_type == "text":
        return _MimoTextEvent(text=part.get("text", ""))

    if msg_type == "reasoning":
        return _MimoReasoningEvent(text=part.get("text", ""))

    if msg_type == "tool_use":
        return _MimoToolUseEvent(
            tool_name=part.get("name", part.get("tool_name", "")),
            tool_id=part.get("id", part.get("tool_id")),
            parameters=part.get("input", part.get("parameters")),
        )

    if msg_type == "tool_result":
        output = part.get("output", part.get("content", ""))
        if isinstance(output, list):
            output = "\n".join(str(item) for item in output)
        return _MimoToolResultEvent(
            output=str(output) if output else "",
            tool_id=part.get("tool_use_id", part.get("tool_id")),
        )

    if msg_type == "step_finish":
        return _MimoStepFinishEvent(
            tokens=part.get("tokens"),
            cost=part.get("cost"),
        )

    if msg_type == "error":
        error = data.get("error", {})
        return _MimoErrorEvent(message=error.get("data", {}).get("message", error.get("message", "")))

    return None


class MimocodeProvider:
    """MiMoCode — Xiaomi's AI coding agent (binary: mimo)."""

    def __init__(
        self,
        model: str | None = None,
        *,
        sandbox: bool = False,
        include_dirs: list[str] | None = None,
        approval_mode: ApprovalMode | None = None,
        agent_name: str | None = None,
        session_name: str | None = None,
        continue_last: bool = False,
        fork_session: bool = False,
        files: list[str] | None = None,
        variant: str | None = None,
        thinking: bool = False,
        # Accepted but not used by MiMoCode CLI — forwarded by Agent
        mcp_servers: list | None = None,
        max_budget_usd: float | None = None,
        system_prompt: str | None = None,
        append_system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        disallowed_tools: list[str] | None = None,
        effort: str | None = None,
        fallback_model: str | None = None,
        json_schema: dict | None = None,
        raw_output: bool = False,
    ) -> None:
        self._model = model or MIMOCODE_DEFAULT_MODEL
        self._sandbox = sandbox
        self._include_dirs = include_dirs or []
        self._approval_mode = approval_mode
        self._agent_name = agent_name
        self._session_name = session_name
        self._continue_last = continue_last
        self._fork_session = fork_session
        self._files = files or []
        self._variant = variant
        self._thinking = thinking
        self._tools = ToolTracker()

    @property
    def binary_name(self) -> str:
        return "mimo"

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
        cmd = [self.binary_name, "run", "--format", "json"]

        if self._approval_mode is None or self._approval_mode in (ApprovalMode.BYPASS, ApprovalMode.YOLO):
            cmd.append("--dangerously-skip-permissions")

        if self._sandbox:
            cmd.append("--sandbox")

        if self._agent_name:
            cmd.extend(["--agent", self._agent_name])

        if self._session_name:
            cmd.extend(["--title", self._session_name])

        if self._thinking:
            cmd.append("--thinking")

        effective_model = model or self._model
        if effective_model:
            cmd.extend(["-m", effective_model])

        if self._variant:
            cmd.extend(["--variant", self._variant])

        if self._include_dirs:
            for d in self._include_dirs:
                cmd.extend(["--dir", d])

        if self._files:
            for f in self._files:
                cmd.extend(["-f", f])

        if session_id:
            cmd.extend(["-s", session_id])

        if self._continue_last:
            cmd.append("-c")

        if self._fork_session and (session_id or self._continue_last):
            cmd.append("--fork")

        cmd.append(prompt)

        return cmd

    def parse_event_line(self, line: str) -> list[AgentEvent]:
        stripped = line.strip()
        if not stripped:
            return []

        parsed = _parse_mimo_line(stripped)
        if parsed is None:
            return [ThinkingEvent(text=stripped)]

        if isinstance(parsed, _MimoTextEvent):
            return [ThinkingEvent(text=parsed.text)]

        if isinstance(parsed, _MimoReasoningEvent):
            return [ThinkingEvent(text=parsed.text)]

        if isinstance(parsed, _MimoToolUseEvent):
            if parsed.tool_id:
                self._tools.record(parsed.tool_id, parsed.tool_name)
            return [
                ToolCallEvent(
                    tool=parsed.tool_name,
                    args=parsed.parameters,
                    tool_id=parsed.tool_id,
                )
            ]

        if isinstance(parsed, _MimoToolResultEvent):
            base = self._tools.resolve(parsed.tool_id)
            return [
                ToolResultEvent(
                    tool=base.tool,
                    output=parsed.output,
                    duration_ms=base.duration_ms,
                )
            ]

        if isinstance(parsed, _MimoStepFinishEvent):
            return [usage_from_step_finish(parsed.tokens or {}, cost=parsed.cost)]

        if isinstance(parsed, _MimoErrorEvent):
            return [ThinkingEvent(text=f"Error: {parsed.message}")]

        return []

    def extract_session_id(self, raw_lines: list[str]) -> str | None:
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                continue
            sid = data.get("sessionID")
            if isinstance(sid, str) and sid:
                return sid
        return None

    def extract_text(self, raw_lines: list[str]) -> str:
        text_parts: list[str] = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            parsed = _parse_mimo_line(stripped)
            if isinstance(parsed, _MimoTextEvent):
                text_parts.append(parsed.text)
        return "".join(text_parts).strip()

    def build_env(self) -> dict[str, str]:
        return default_build_env()


class MimocodeAutoProvider(MimocodeProvider):
    """MiMoCode Auto — default model (mimo/mimo-auto)."""

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(model=model or "mimo/mimo-auto", **kwargs)


class MimocodeV2ProProvider(MimocodeProvider):
    """MiMoCode V2 Pro — Xiaomi's flagship model (xiaomi/mimo-v2.5-pro)."""

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(model=model or "xiaomi/mimo-v2.5-pro", **kwargs)


class MimocodeV2FlashProvider(MimocodeProvider):
    """MiMoCode V2 Flash — fast model (xiaomi/mimo-v2-flash)."""

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(model=model or "xiaomi/mimo-v2-flash", **kwargs)
