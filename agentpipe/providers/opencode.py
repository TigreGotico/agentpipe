from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .._types import (
    AgentEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    UsageEvent,
)

OPENCODE_FREE_DEFAULT_MODEL = "opencode/big-pickle"
OPENCODE_ZEN_DEFAULT_MODEL = "opencode/gemini-3-flash"
OPENCODE_GO_DEFAULT_MODEL = "opencode-go/deepseek-v4-flash"


@dataclass
class _OpencodeTextEvent:
    text: str = ""


@dataclass
class _OpencodeToolUseEvent:
    tool_name: str = ""
    input_data: Any = None
    output_data: Any = None
    status: str = ""


@dataclass
class _OpencodeStepStartEvent:
    pass


@dataclass
class _OpencodeStepFinishEvent:
    reason: str | None = None
    cost: float | None = None
    tokens: dict[str, Any] | None = None


_OpencodeParsedEvent = (
    "_OpencodeTextEvent | _OpencodeToolUseEvent | _OpencodeStepStartEvent | _OpencodeStepFinishEvent | None"
)


def _parse_opencode_line(
    line: str,
) -> _OpencodeTextEvent | _OpencodeToolUseEvent | _OpencodeStepStartEvent | _OpencodeStepFinishEvent | None:
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    msg_type = data.get("type")
    part = data.get("part", {})

    if msg_type == "text":
        return _OpencodeTextEvent(text=part.get("text", ""))
    if msg_type == "tool_use":
        state = data.get("state", {})
        return _OpencodeToolUseEvent(
            tool_name=part.get("tool", ""),
            input_data=state.get("input"),
            output_data=state.get("output"),
            status=state.get("status", ""),
        )
    if msg_type == "step_start":
        return _OpencodeStepStartEvent()
    if msg_type == "step_finish":
        return _OpencodeStepFinishEvent(
            reason=part.get("reason"),
            cost=part.get("cost"),
            tokens=part.get("tokens"),
        )

    return None


class OpencodeProvider:
    """Base / backward-compat opencode provider (alias for Zen plan)."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or OPENCODE_ZEN_DEFAULT_MODEL

    @property
    def binary_name(self) -> str:
        return "opencode"

    @property
    def model(self) -> str | None:
        return self._model

    @property
    def plan(self) -> str:
        return "zen"

    def build_command(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        model: str | None = None,
    ) -> list[str]:
        cmd = [self.binary_name, "run"]
        if session_id:
            cmd.extend(["--session", session_id])
        cmd.append(prompt)
        effective_model = model or self._model
        if effective_model:
            cmd.extend(["--model", effective_model])
        cmd.append("--format=json")
        return cmd

    def parse_event_line(self, line: str) -> list[AgentEvent]:
        stripped = line.strip()
        if not stripped:
            return []

        parsed = _parse_opencode_line(stripped)
        if parsed is None:
            return [ThinkingEvent(text=stripped)]

        if isinstance(parsed, _OpencodeTextEvent):
            return [ThinkingEvent(text=parsed.text)]

        if isinstance(parsed, _OpencodeToolUseEvent):
            if parsed.status in ("success", "error"):
                args = parsed.input_data
                if isinstance(args, dict):
                    args = {str(k): v for k, v in args.items()}
                else:
                    args = {"input": args}
                output = str(parsed.output_data) if parsed.output_data is not None else ""
                return [
                    ToolResultEvent(
                        tool=parsed.tool_name,
                        output=output,
                    )
                ]
            if parsed.tool_name and parsed.input_data is not None:
                args = parsed.input_data
                if isinstance(args, dict):
                    args = {str(k): v for k, v in args.items()}
                return [
                    ToolCallEvent(
                        tool=parsed.tool_name,
                        args=args,
                    )
                ]
            return []

        if isinstance(parsed, _OpencodeStepFinishEvent):
            tokens = parsed.tokens or {}
            cache = tokens.get("cache") or {}
            cache_read = int(cache.get("read") or 0)
            cache_write = int(cache.get("write") or 0)
            cached = cache_read + cache_write
            return [
                UsageEvent(
                    input_tokens=int(tokens.get("input") or 0) + cached,
                    output_tokens=int(tokens.get("output") or 0) + int(tokens.get("reasoning") or 0),
                    cost_usd=parsed.cost,
                    cache_read_tokens=cache_read,
                    cache_write_tokens=cache_write,
                )
            ]

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
            parsed = _parse_opencode_line(stripped)
            if isinstance(parsed, _OpencodeTextEvent):
                text_parts.append(parsed.text)
        return "".join(text_parts).strip()

    def build_env(self) -> dict[str, str]:
        import os

        return dict(os.environ)


class OpencodeFreeProvider(OpencodeProvider):
    """Opencode Free plan — free-tier models via the Zen endpoint (opencode/ prefix)."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or OPENCODE_FREE_DEFAULT_MODEL

    @property
    def plan(self) -> str:
        return "free"


class OpencodeZenProvider(OpencodeProvider):
    """Opencode Zen plan — pay-as-you-go via the Zen endpoint (opencode/ prefix)."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or OPENCODE_ZEN_DEFAULT_MODEL

    @property
    def plan(self) -> str:
        return "zen"


class OpencodeGoProvider(OpencodeProvider):
    """Opencode Go plan — subscription via the Go endpoint (opencode-go/ prefix).

    Same binary, but models use the opencode-go/ prefix which routes to
    https://opencode.ai/zen/go/v1 with its own rate limits and flat billing.
    """

    def __init__(self, model: str | None = None) -> None:
        self._model = model or OPENCODE_GO_DEFAULT_MODEL

    @property
    def plan(self) -> str:
        return "go"
