from __future__ import annotations

import json

from .._types import (
    AgentEvent,
    ApprovalMode,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    UsageEvent,
)

KILO_DEFAULT_MODEL = "kilo/kilo-auto/free"

_OPENCODE_EFFORT_MAP = {
    "low": "minimal",
    "medium": "low",
    "high": "high",
    "xhigh": "max",
    "max": "max",
}


def _parse_kilo_line(line: str) -> dict | None:
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    return data


class KiloProvider:
    """Kilo Code — all-in-one agentic engineering platform (binary: kilo).

    Fork of OpenCode with Kilo's own model gateway. Free tier available
    with free AI models or BYOK (bring your own keys).
    """

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
        show_thinking: bool = False,
        # Accepted but not used by Kilo CLI — forwarded by Agent
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
        self._model = model or KILO_DEFAULT_MODEL
        self._sandbox = sandbox
        self._include_dirs = include_dirs
        self._approval_mode = approval_mode
        self._effort = effort
        self._agent_name = agent_name
        self._session_name = session_name
        self._continue_last = continue_last
        self._fork_session = fork_session
        self._files = files
        self._show_thinking = show_thinking

    @property
    def binary_name(self) -> str:
        return "kilo"

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
        cmd = [self.binary_name, "run", prompt]

        if session_id:
            cmd.extend(["--session", session_id])
        if self._continue_last:
            cmd.append("--continue")
        if self._fork_session:
            cmd.append("--fork")
        if self._approval_mode is None or self._approval_mode in (ApprovalMode.BYPASS, ApprovalMode.YOLO):
            cmd.append("--dangerously-skip-permissions")
        else:
            cmd.append("--auto")
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
            variant = _OPENCODE_EFFORT_MAP.get(self._effort, self._effort)
            cmd.extend(["--variant", variant])
        if self._include_dirs:
            for d in self._include_dirs:
                cmd.extend(["--dir", d])
        if self._files:
            for f in self._files:
                cmd.extend(["--file", f])
        if self._show_thinking:
            cmd.append("--thinking")
        cmd.append("--format=json")
        return cmd

    def parse_event_line(self, line: str) -> list[AgentEvent]:
        stripped = line.strip()
        if not stripped:
            return []

        parsed = _parse_kilo_line(stripped)
        if parsed is None:
            return [ThinkingEvent(text=stripped)]

        msg_type = parsed.get("type")
        part = parsed.get("part", {})

        if msg_type == "text":
            return [ThinkingEvent(text=part.get("text", ""))]

        if msg_type == "tool_use":
            state = parsed.get("state", {})
            status = state.get("status", "")
            tool_name = part.get("tool", "")

            if status in ("success", "error"):
                args = state.get("input")
                if isinstance(args, dict):
                    args = {str(k): v for k, v in args.items()}
                else:
                    args = {"input": args}
                output = str(state.get("output", "")) if state.get("output") is not None else ""
                return [
                    ToolResultEvent(
                        tool=tool_name,
                        output=output,
                    )
                ]
            if tool_name and state.get("input") is not None:
                args = state.get("input")
                if isinstance(args, dict):
                    args = {str(k): v for k, v in args.items()}
                return [
                    ToolCallEvent(
                        tool=tool_name,
                        args=args,
                    )
                ]
            return []

        if msg_type == "step_finish":
            tokens = part.get("tokens") or {}
            cache = tokens.get("cache") or {}
            cache_read = int(cache.get("read") or 0)
            cache_write = int(cache.get("write") or 0)
            cached = cache_read + cache_write
            return [
                UsageEvent(
                    input_tokens=int(tokens.get("input") or 0) + cached,
                    output_tokens=int(tokens.get("output") or 0) + int(tokens.get("reasoning") or 0),
                    cost_usd=part.get("cost"),
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
            data = _parse_kilo_line(stripped)
            if data is None:
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
            data = _parse_kilo_line(stripped)
            if data is None:
                text_parts.append(stripped)
            elif data.get("type") == "text":
                text_parts.append(data.get("part", {}).get("text", ""))
        return "".join(text_parts).strip()

    def build_env(self) -> dict[str, str]:
        import os

        return dict(os.environ)
