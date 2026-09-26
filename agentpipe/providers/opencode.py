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
from ._utils import EFFORT_VARIANT_MAP, default_build_env, extract_session_id_from_json, usage_from_step_finish

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

    def __init__(
        self,
        model: str | None = None,
        *,
        sandbox: bool = False,
        include_dirs: list[str] | None = None,
        approval_mode: ApprovalMode | None = None,
        effort: str | None = None,
        agent_name: str | None = None,
        session_name: str | None = None,
        continue_last: bool = False,
        fork_session: bool = False,
        files: list[str] | None = None,
        # Accepted but not used by OpenCode CLI — forwarded by Agent
        mcp_servers: list | None = None,
        max_budget_usd: float | None = None,
        system_prompt: str | None = None,
        append_system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        disallowed_tools: list[str] | None = None,
        fallback_model: str | None = None,
        json_schema: dict | None = None,
        raw_output: bool = False,
    ) -> None:
        self._model = model or OPENCODE_ZEN_DEFAULT_MODEL
        self._sandbox = sandbox
        self._include_dirs = include_dirs
        self._approval_mode = approval_mode
        self._effort = effort
        self._agent_name = agent_name
        self._session_name = session_name
        self._continue_last = continue_last
        self._fork_session = fork_session
        self._files = files

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
        if self._continue_last:
            cmd.append("--continue")
        if self._fork_session:
            cmd.append("--fork")
        if self._approval_mode is None or self._approval_mode in (ApprovalMode.BYPASS, ApprovalMode.YOLO):
            cmd.append("--dangerously-skip-permissions")
        if self._sandbox:
            cmd.append("--sandbox")
        if self._agent_name:
            cmd.extend(["--agent", self._agent_name])
        if self._session_name:
            cmd.extend(["--title", self._session_name])
        effective_model = model or self._model
        if effective_model:
            cmd.extend(["--model", effective_model])
        if self._effort:
            variant = EFFORT_VARIANT_MAP.get(self._effort, self._effort)
            cmd.extend(["--variant", variant])
        if self._include_dirs:
            for d in self._include_dirs:
                cmd.extend(["--dir", d])
        if self._files:
            for f in self._files:
                cmd.extend(["--file", f])
        cmd.append(prompt)
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
            return [usage_from_step_finish(parsed.tokens or {}, cost=parsed.cost)]

        return []

    def extract_session_id(self, raw_lines: list[str]) -> str | None:
        return extract_session_id_from_json(raw_lines, keys=("sessionID",))

    def detect_error(self, raw_lines: list[str]) -> str | None:
        """This CLI reports its failures through a non-zero exit code."""
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
        return default_build_env()


class OpencodeFreeProvider(OpencodeProvider):
    """Opencode Free plan — free-tier models via the Zen endpoint (opencode/ prefix)."""

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(model=model or OPENCODE_FREE_DEFAULT_MODEL, **kwargs)

    @property
    def plan(self) -> str:
        return "free"


class OpencodeZenProvider(OpencodeProvider):
    """Opencode Zen plan — pay-as-you-go via the Zen endpoint (opencode/ prefix)."""

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(model=model or OPENCODE_ZEN_DEFAULT_MODEL, **kwargs)

    @property
    def plan(self) -> str:
        return "zen"


class OpencodeGoProvider(OpencodeProvider):
    """Opencode Go plan — subscription via the Go endpoint (opencode-go/ prefix).

    Same binary, but models use the opencode-go/ prefix which routes to
    https://opencode.ai/zen/go/v1 with its own rate limits and flat billing.
    """

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(model=model or OPENCODE_GO_DEFAULT_MODEL, **kwargs)

    @property
    def plan(self) -> str:
        return "go"
