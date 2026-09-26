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
    UsageEvent,
)
from ._utils import ToolTracker, default_build_env, extract_session_id_from_json

VIBE_DEFAULT_MODEL = "mistral-large-latest"

_VIBE_APPROVAL_MAP: dict[ApprovalMode, str] = {
    ApprovalMode.DEFAULT: "default",
    ApprovalMode.AUTO_EDIT: "accept-edits",
    ApprovalMode.YOLO: "auto-approve",
    ApprovalMode.PLAN: "plan",
    ApprovalMode.BYPASS: "auto-approve",
}


@dataclass
class _VibeTextEvent:
    text: str = ""


@dataclass
class _VibeToolUseEvent:
    tool_name: str = ""
    tool_id: str | None = None
    parameters: Any = None


@dataclass
class _VibeToolResultEvent:
    output: str = ""
    tool_id: str | None = None


@dataclass
class _VibeUsageEvent:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None


def _parse_vibe_line(
    line: str,
) -> _VibeTextEvent | _VibeToolUseEvent | _VibeToolResultEvent | _VibeUsageEvent | None:
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    msg_type = data.get("type")

    if msg_type == "text":
        return _VibeTextEvent(text=data.get("content", data.get("text", "")))
    if msg_type == "tool_use":
        return _VibeToolUseEvent(
            tool_name=data.get("name", data.get("tool_name", "")),
            tool_id=data.get("id", data.get("tool_id")),
            parameters=data.get("input", data.get("parameters")),
        )
    if msg_type == "tool_result":
        output = data.get("output", data.get("content", ""))
        if isinstance(output, list):
            output = "\n".join(str(item) for item in output)
        return _VibeToolResultEvent(
            output=str(output) if output else "",
            tool_id=data.get("tool_use_id", data.get("tool_id")),
        )
    if msg_type == "usage":
        return _VibeUsageEvent(
            input_tokens=int(data.get("input_tokens", data.get("prompt_tokens", 0))),
            output_tokens=int(data.get("output_tokens", data.get("completion_tokens", 0))),
            cost_usd=data.get("cost_usd") if isinstance(data.get("cost_usd"), (int, float)) else None,
        )
    return None


class VibeProvider:
    """Mistral Vibe — open-source CLI coding agent (binary: vibe)."""

    def __init__(
        self,
        model: str | None = None,
        *,
        sandbox: bool = False,
        include_dirs: list[str] | None = None,
        approval_mode: ApprovalMode | None = None,
        allowed_tools: list[str] | None = None,
        session_name: str | None = None,
        continue_last: bool = False,
        max_turns: int | None = None,
        max_price: float | None = None,
        max_tokens: int | None = None,
        # Accepted but not used by Vibe CLI — forwarded by Agent
        mcp_servers: list | None = None,
        max_budget_usd: float | None = None,
        system_prompt: str | None = None,
        append_system_prompt: str | None = None,
        disallowed_tools: list[str] | None = None,
        effort: str | None = None,
        fallback_model: str | None = None,
        json_schema: dict | None = None,
        agent_name: str | None = None,
        raw_output: bool = False,
        fork_session: bool = False,
        files: list[str] | None = None,
    ) -> None:
        self._model = model or VIBE_DEFAULT_MODEL
        self._sandbox = sandbox
        self._include_dirs = include_dirs or []
        self._approval_mode = approval_mode
        self._allowed_tools = allowed_tools
        self._session_name = session_name
        self._continue_last = continue_last
        self._max_turns = max_turns
        self._max_price = max_price
        self._max_tokens = max_tokens
        self._tools = ToolTracker()

    @property
    def binary_name(self) -> str:
        return "vibe"

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
        cmd = [self.binary_name, "--prompt", prompt]
        if self._approval_mode is not None:
            agent_name = _VIBE_APPROVAL_MAP.get(self._approval_mode, "default")
            cmd.extend(["--agent", agent_name])
        effective_model = model or self._model
        if effective_model:
            cmd.extend(["--model", effective_model])
        if self._sandbox:
            cmd.append("--sandbox")
        if self._include_dirs:
            for d in self._include_dirs:
                cmd.extend(["--add-dir", d])
        if self._allowed_tools:
            for tool in self._allowed_tools:
                cmd.extend(["--enabled-tools", tool])
        if self._session_name:
            cmd.extend(["--workdir", self._session_name])
        if self._continue_last:
            cmd.append("--continue")
        if session_id:
            cmd.extend(["--resume", session_id])
        if self._max_turns is not None:
            cmd.extend(["--max-turns", str(self._max_turns)])
        if self._max_price is not None:
            cmd.extend(["--max-price", str(self._max_price)])
        if self._max_tokens is not None:
            cmd.extend(["--max-tokens", str(self._max_tokens)])
        cmd.extend(["--output", "streaming"])
        return cmd

    def parse_event_line(self, line: str) -> list[AgentEvent]:
        stripped = line.strip()
        if not stripped:
            return []

        parsed = _parse_vibe_line(stripped)
        if parsed is None:
            return [ThinkingEvent(text=stripped)]

        if isinstance(parsed, _VibeTextEvent):
            return [ThinkingEvent(text=parsed.text)]

        if isinstance(parsed, _VibeToolUseEvent):
            if parsed.tool_id:
                self._tools.record(parsed.tool_id, parsed.tool_name)
            return [
                ToolCallEvent(
                    tool=parsed.tool_name,
                    args=parsed.parameters,
                    tool_id=parsed.tool_id,
                )
            ]

        if isinstance(parsed, _VibeToolResultEvent):
            base = self._tools.resolve(parsed.tool_id)
            return [
                ToolResultEvent(
                    tool=base.tool,
                    output=parsed.output,
                    duration_ms=base.duration_ms,
                )
            ]

        if isinstance(parsed, _VibeUsageEvent):
            return [
                UsageEvent(
                    input_tokens=parsed.input_tokens,
                    output_tokens=parsed.output_tokens,
                    cost_usd=parsed.cost_usd,
                )
            ]

        return []

    def extract_session_id(self, raw_lines: list[str]) -> str | None:
        return extract_session_id_from_json(raw_lines)

    def detect_error(self, raw_lines: list[str]) -> str | None:
        """This CLI reports its failures through a non-zero exit code."""
        return None

    def extract_text(self, raw_lines: list[str]) -> str:
        text_parts: list[str] = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            parsed = _parse_vibe_line(stripped)
            if isinstance(parsed, _VibeTextEvent):
                text_parts.append(parsed.text)
        return "".join(text_parts).strip()

    def build_env(self) -> dict[str, str]:
        return default_build_env()
