from __future__ import annotations

import re

from .._types import (
    AgentEvent,
    ApprovalMode,
    ThinkingEvent,
    UsageEvent,
)

AIDER_DEFAULT_MODEL = "openrouter/google/gemma-4-26b-a4b-it:free"

_AIDER_HEADER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p)
    for p in [
        r"^Aider v\d",
        r"^Model:",
        r"^Git repo:",
        r"^Repo-map:",
        r"^https://aider",
        r"^Warning:",
        r"^Added ",
        r"^Git repository",
        r"^litellm\.",
        r"^Tokens:",
        r"^Did you mean",
        r"^You can skip",
        r"^\d+/\d+ \(creates|updates|reads\)",
        r"^ℹ ",
        r"^✓ ",
        r"^! ",
    ]
]

_TOKENS_RE = re.compile(r"Tokens:\s*(\d+)\s+sent,\s*(\d+)\s+received")


def _is_aider_header(line: str) -> bool:
    return any(p.match(line) for p in _AIDER_HEADER_PATTERNS)


def _parse_tokens_line(line: str) -> UsageEvent | None:
    m = _TOKENS_RE.match(line)
    if m:
        return UsageEvent(
            input_tokens=int(m.group(1)),
            output_tokens=int(m.group(2)),
        )
    return None


class AiderProvider:
    """Aider — AI pair programming in your terminal (binary: aider).

    Uses OpenRouter free tier by default. Supports all major LLM providers
    via LiteLLM (OpenAI, Anthropic, Google, DeepSeek, local Ollama, etc.).
    """

    def __init__(
        self,
        model: str | None = None,
        *,
        files: list[str] | None = None,
        read_files: list[str] | None = None,
        architect: bool = False,
        edit_format: str | None = None,
        weak_model: str | None = None,
        reasoning_effort: str | None = None,
        thinking_tokens: int | None = None,
        cache_prompts: bool = False,
        map_tokens: int | None = None,
        auto_commits: bool = True,
        git: bool = True,
        dry_run: bool = False,
        show_diffs: bool = False,
        lint: bool = False,
        test: bool = False,
        lint_cmd: list[str] | None = None,
        test_cmd: str | None = None,
        auto_lint: bool = True,
        auto_test: bool = False,
        api_key: list[str] | None = None,
        set_env: list[str] | None = None,
        api_timeout: int | None = None,
        verbose: bool = False,
        effort: str | None = None,
        approval_mode: ApprovalMode | None = None,
        mcp_servers: list | None = None,
        max_budget_usd: float | None = None,
        system_prompt: str | None = None,
        append_system_prompt: str | None = None,
        allowed_tools: list[str] | None = None,
        disallowed_tools: list[str] | None = None,
        fallback_model: str | None = None,
        json_schema: dict | None = None,
        session_name: str | None = None,
        agent_name: str | None = None,
        sandbox: bool = False,
        raw_output: bool = False,
        include_dirs: list[str] | None = None,
        continue_last: bool = False,
        fork_session: bool = False,
    ) -> None:
        self._model = model or AIDER_DEFAULT_MODEL
        self._files = files or []
        self._read_files = read_files or []
        self._architect = architect
        self._edit_format = edit_format
        self._weak_model = weak_model
        self._reasoning_effort = reasoning_effort or effort
        self._thinking_tokens = thinking_tokens
        self._cache_prompts = cache_prompts
        self._map_tokens = map_tokens
        self._auto_commits = auto_commits
        self._git = git
        self._dry_run = dry_run
        self._show_diffs = show_diffs
        self._lint = lint
        self._test = test
        self._lint_cmd = lint_cmd or []
        self._test_cmd = test_cmd
        self._auto_lint = auto_lint
        self._auto_test = auto_test
        self._api_key = api_key or []
        self._set_env = set_env or []
        self._api_timeout = api_timeout
        self._verbose = verbose

    @property
    def binary_name(self) -> str:
        return "aider"

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

        cmd.extend(["--message", prompt])

        cmd.extend([
            "--yes-always", "--no-pretty", "--no-stream",
            "--no-check-update", "--no-show-model-warnings",
        ])

        effective_model = model or self._model
        cmd.extend(["--model", effective_model])

        for f in self._files:
            cmd.extend(["--file", f])
        for f in self._read_files:
            cmd.extend(["--read", f])

        if self._architect:
            cmd.append("--architect")
        if self._edit_format:
            cmd.extend(["--edit-format", self._edit_format])
        if self._weak_model:
            cmd.extend(["--weak-model", self._weak_model])
        if self._reasoning_effort:
            cmd.extend(["--reasoning-effort", self._reasoning_effort])
        if self._thinking_tokens is not None:
            cmd.extend(["--thinking-tokens", str(self._thinking_tokens)])
        if self._cache_prompts:
            cmd.append("--cache-prompts")
        if self._map_tokens is not None:
            cmd.extend(["--map-tokens", str(self._map_tokens)])
        if not self._git:
            cmd.append("--no-git")
        if not self._auto_commits:
            cmd.append("--no-auto-commits")
        if self._dry_run:
            cmd.append("--dry-run")
        if self._show_diffs:
            cmd.append("--show-diffs")
        if self._lint:
            cmd.append("--lint")
        if self._test:
            cmd.append("--test")
        for lc in self._lint_cmd:
            cmd.extend(["--lint-cmd", lc])
        if self._test_cmd:
            cmd.extend(["--test-cmd", self._test_cmd])
        if not self._auto_lint:
            cmd.append("--no-auto-lint")
        if self._auto_test:
            cmd.append("--auto-test")
        for ak in self._api_key:
            cmd.extend(["--api-key", ak])
        for se in self._set_env:
            cmd.extend(["--set-env", se])
        if self._api_timeout is not None:
            cmd.extend(["--timeout", str(self._api_timeout)])
        if self._verbose:
            cmd.append("-v")

        return cmd

    def parse_event_line(self, line: str) -> list[AgentEvent]:
        stripped = line.strip()
        if not stripped:
            return []
        if _is_aider_header(stripped):
            usage = _parse_tokens_line(stripped)
            if usage:
                return [usage]
            return []
        return [ThinkingEvent(text=stripped)]

    def extract_session_id(self, raw_lines: list[str]) -> str | None:
        return None

    def extract_text(self, raw_lines: list[str]) -> str:
        parts: list[str] = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            if not _is_aider_header(stripped):
                parts.append(stripped)
        return "\n".join(parts)

    def build_env(self) -> dict[str, str]:
        import os

        return dict(os.environ)
