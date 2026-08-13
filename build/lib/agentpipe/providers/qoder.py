from __future__ import annotations

import json

from .._types import (
    AgentEvent,
    ApprovalMode,
    McpServerConfig,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from ._utils import (
    ToolTracker,
    build_mcp_config_json,
    default_build_env,
    extract_session_id_from_json,
    usage_from_anthropic,
)

QODER_DEFAULT_MODEL = None

_APPROVAL_MODE_MAP: dict[ApprovalMode, str] = {
    ApprovalMode.DEFAULT: "default",
    ApprovalMode.AUTO_EDIT: "accept_edits",
    ApprovalMode.YOLO: "bypass_permissions",
    ApprovalMode.PLAN: "plan",
    ApprovalMode.BYPASS: "bypass_permissions",
}


class QoderProvider:
    """QoderCLI — coding agent CLI from Qoder AI (binary: qodercli).

    CLI flags mirror Claude Code's interface closely (same --output-format,
    --dangerously-skip-permissions, --permission-mode, etc.) since QoderCLI
    is a fork/clone architecture.
    """

    def __init__(
        self,
        model: str | None = None,
        *,
        mcp_servers: list[McpServerConfig] | None = None,
        approval_mode: ApprovalMode | None = None,
        max_budget_usd: float | None = None,
        system_prompt: str | None = None,
        append_system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        disallowed_tools: list[str] | None = None,
        agent_name: str | None = None,
        sandbox: bool = False,
        raw_output: bool = False,
        include_dirs: list[str] | None = None,
        session_name: str | None = None,
        continue_last: bool = False,
        fork_session: bool = False,
        files: list[str] | None = None,
        max_turns: int | None = None,
        effort: str | None = None,
        fallback_model: str | None = None,
        json_schema: dict | None = None,
    ) -> None:
        self._model = model
        self._mcp_servers = mcp_servers or []
        self._approval_mode = approval_mode
        self._max_budget_usd = max_budget_usd
        self._system_prompt = system_prompt
        self._append_system_prompt = append_system_prompt
        self._allowed_tools = allowed_tools
        self._disallowed_tools = disallowed_tools
        self._agent_name = agent_name
        self._sandbox = sandbox
        self._raw_output = raw_output
        self._include_dirs = include_dirs
        self._session_name = session_name
        self._continue_last = continue_last
        self._fork_session = fork_session
        self._files = files
        self._max_turns = max_turns
        self._effort = effort
        self._fallback_model = fallback_model
        self._json_schema = json_schema
        self._tools = ToolTracker(thread_safe=True)

    @property
    def binary_name(self) -> str:
        return "qodercli"

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
        skips_permissions = (
            self._approval_mode is None
            or self._approval_mode == ApprovalMode.BYPASS
            or self._approval_mode == ApprovalMode.YOLO
        )
        cmd = [
            self.binary_name,
            "-p",
            "--dangerously-skip-permissions" if skips_permissions else "--permission-mode",
        ]

        if self._approval_mode is not None and self._approval_mode not in (ApprovalMode.BYPASS, ApprovalMode.YOLO):
            cmd.pop()
            cmd.extend(["--permission-mode", _APPROVAL_MODE_MAP[self._approval_mode]])

        if self._system_prompt:
            cmd.extend(["--system-prompt", self._system_prompt])
        if self._append_system_prompt:
            cmd.extend(["--append-system-prompt", self._append_system_prompt])
        if self._allowed_tools:
            for tool in self._allowed_tools:
                cmd.extend(["--allowed-tools", tool])
        if self._disallowed_tools:
            for tool in self._disallowed_tools:
                cmd.extend(["--disallowed-tools", tool])
        if self._effort:
            cmd.extend(["--effort", self._effort])
        if self._fallback_model:
            cmd.extend(["--fallback-model", self._fallback_model])
        if self._json_schema:
            cmd.extend(["--output-format", "json", "--json-schema", json.dumps(self._json_schema)])
        elif not self._raw_output:
            cmd.extend(["--output-format", "stream-json", "--verbose"])
        else:
            cmd.extend(["--output-format", "stream-json"])

        if session_id:
            cmd.extend(["--resume", session_id])
        if self._continue_last:
            cmd.append("--continue")
        if self._fork_session:
            cmd.append("--fork-session")
        if self._sandbox:
            cmd.append("--sandbox")
        if self._agent_name:
            cmd.extend(["--agent", self._agent_name])
        if self._session_name:
            cmd.extend(["--name", self._session_name])
        if self._include_dirs:
            for d in self._include_dirs:
                cmd.extend(["--add-dir", d])
        if self._files:
            for f in self._files:
                cmd.extend(["--file", f])
        if self._max_turns is not None:
            cmd.extend(["--max-turns", str(self._max_turns)])

        cmd.append(prompt)

        effective_model = model or self._model
        if effective_model:
            cmd.extend(["--model", effective_model])

        if self._mcp_servers:
            cmd.extend(["--mcp-config", build_mcp_config_json(self._mcp_servers), "--strict-mcp-config"])

        if self._max_budget_usd is not None:
            cmd.extend(["--max-budget-usd", str(self._max_budget_usd)])

        return cmd

    def parse_event_line(self, line: str) -> list[AgentEvent]:
        stripped = line.strip()
        if not stripped:
            return []

        try:
            data = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return [ThinkingEvent(text=stripped)]

        event_type = data.get("type")

        if event_type in ("text", "assistant"):
            content = data.get("content", data.get("text", ""))
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                content = "".join(parts)
            return [ThinkingEvent(text=str(content))]

        if event_type == "tool_use":
            tool_name = data.get("name", data.get("tool_name", ""))
            tool_id = data.get("id", data.get("tool_id"))
            params = data.get("input", data.get("parameters"))
            if tool_id:
                self._tools.record(tool_id, tool_name)
            return [
                ToolCallEvent(
                    tool=tool_name,
                    args=params,
                    tool_id=tool_id,
                )
            ]

        if event_type == "tool_result":
            output = data.get("output", data.get("content", ""))
            if isinstance(output, list):
                output = "\n".join(str(item) for item in output)
            tool_id = data.get("tool_use_id", data.get("tool_id"))
            base = self._tools.resolve(tool_id)
            return [
                ToolResultEvent(
                    tool=base.tool,
                    output=str(output) if output else "",
                    duration_ms=base.duration_ms,
                )
            ]

        if event_type == "result":
            cost = data["total_cost_usd"] if isinstance(data.get("total_cost_usd"), (int, float)) else None
            return [usage_from_anthropic(data.get("usage") or {}, cost_usd=cost)]

        if event_type == "system":
            return []

        return []

    def extract_session_id(self, raw_lines: list[str]) -> str | None:
        return extract_session_id_from_json(raw_lines)

    def extract_text(self, raw_lines: list[str]) -> str:
        text_parts: list[str] = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                continue
            event_type = data.get("type")
            if event_type in ("text", "assistant"):
                content = data.get("content", data.get("text", ""))
                if isinstance(content, list):
                    text_parts.extend(
                        block.get("text", "")
                        for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
                elif isinstance(content, str):
                    text_parts.append(content)
            elif event_type == "result":
                result = data.get("result", "")
                if result:
                    return str(result)
        return "".join(text_parts).strip()

    def build_env(self) -> dict[str, str]:
        return default_build_env()
