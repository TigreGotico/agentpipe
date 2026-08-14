from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from typing import Any

from .._types import (
    AgentEvent,
    ApprovalMode,
    ThinkingEvent,
)
from ._utils import default_build_env

ANTIGRAVITY_DEFAULT_MODEL = "Gemini 3.5 Flash (Medium)"


class AntigravityProvider:
    """Antigravity — Google DeepMind coding assistant CLI (binary: agy)."""

    def __init__(
        self,
        model: str | None = None,
        *,
        mcp_servers: list[Any] | None = None,
        approval_mode: ApprovalMode | None = None,
        max_budget_usd: float | None = None,
        system_prompt: str | None = None,
        append_system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        disallowed_tools: list[str] | None = None,
        effort: str | None = None,
        fallback_model: str | None = None,
        json_schema: dict | None = None,
        agent_name: str | None = None,
        sandbox: bool = False,
        raw_output: bool = False,
        include_dirs: list[str] | None = None,
        session_name: str | None = None,
        continue_last: bool = False,
        fork_session: bool = False,
        files: list[str] | None = None,
    ) -> None:
        self._model = model or ANTIGRAVITY_DEFAULT_MODEL
        self._approval_mode = approval_mode
        self._sandbox = sandbox
        self._include_dirs = include_dirs or []
        self._continue_last = continue_last
        self._last_log_file: str | None = None

    def __del__(self) -> None:
        if hasattr(self, "_last_log_file") and self._last_log_file:
            try:
                if os.path.exists(self._last_log_file):
                    os.remove(self._last_log_file)
            except Exception:
                pass

    @property
    def binary_name(self) -> str:
        return "agy"

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

        skips_permissions = (
            self._approval_mode is None
            or self._approval_mode == ApprovalMode.BYPASS
            or self._approval_mode == ApprovalMode.YOLO
        )
        if skips_permissions:
            cmd.append("--dangerously-skip-permissions")

        effective_model = model or self._model
        if effective_model:
            cmd.extend(["--model", effective_model])

        if self._sandbox:
            cmd.append("--sandbox")

        if self._include_dirs:
            for d in self._include_dirs:
                cmd.extend(["--add-dir", d])

        if session_id:
            cmd.extend(["--conversation", session_id])
        elif self._continue_last:
            cmd.append("--continue")

        # Create a unique temp log file to extract conversation ID
        log_fd, log_path = tempfile.mkstemp(prefix="agy_", suffix=".log")
        os.close(log_fd)
        self._last_log_file = log_path
        cmd.extend(["--log-file", log_path])

        cmd.extend(["--print", prompt])
        return cmd

    def parse_event_line(self, line: str) -> list[AgentEvent]:
        stripped = line.strip()
        if not stripped:
            return []
        return [ThinkingEvent(text=stripped)]

    def extract_session_id(self, raw_lines: list[str]) -> str | None:
        if not hasattr(self, "_last_log_file") or not self._last_log_file:
            return None
        try:
            if os.path.exists(self._last_log_file):
                with open(self._last_log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                match = re.search(r"Created conversation\s+([a-f0-9\-]+)", content)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    def extract_text(self, raw_lines: list[str]) -> str:
        return "\n".join(line.rstrip("\r\n") for line in raw_lines).strip()

    def build_env(self) -> dict[str, str]:
        return default_build_env()


class AntigravityFlashMediumProvider(AntigravityProvider):
    """Antigravity Gemini 3.5 Flash (Medium) model."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("model", "Gemini 3.5 Flash (Medium)")
        super().__init__(**kwargs)


class AntigravityFlashHighProvider(AntigravityProvider):
    """Antigravity Gemini 3.5 Flash (High) model."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("model", "Gemini 3.5 Flash (High)")
        super().__init__(**kwargs)


class AntigravityFlashLowProvider(AntigravityProvider):
    """Antigravity Gemini 3.5 Flash (Low) model."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("model", "Gemini 3.5 Flash (Low)")
        super().__init__(**kwargs)


class AntigravityProLowProvider(AntigravityProvider):
    """Antigravity Gemini 3.1 Pro (Low) model."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("model", "Gemini 3.1 Pro (Low)")
        super().__init__(**kwargs)


class AntigravityProHighProvider(AntigravityProvider):
    """Antigravity Gemini 3.1 Pro (High) model."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("model", "Gemini 3.1 Pro (High)")
        super().__init__(**kwargs)


class AntigravityClaudeSonnetProvider(AntigravityProvider):
    """Antigravity Claude Sonnet 4.6 (Thinking) model."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("model", "Claude Sonnet 4.6 (Thinking)")
        super().__init__(**kwargs)


class AntigravityClaudeOpusProvider(AntigravityProvider):
    """Antigravity Claude Opus 4.6 (Thinking) model."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("model", "Claude Opus 4.6 (Thinking)")
        super().__init__(**kwargs)


class AntigravityGptOssProvider(AntigravityProvider):
    """Antigravity GPT-OSS 120B (Medium) model."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("model", "GPT-OSS 120B (Medium)")
        super().__init__(**kwargs)
