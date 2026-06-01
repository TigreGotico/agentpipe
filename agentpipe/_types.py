from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Provider(str, Enum):
    CLAUDE = "claude"
    GEMINI = "gemini"
    OPENCODE = "opencode"


@dataclass(frozen=True)
class ThinkingEvent:
    text: str


@dataclass(frozen=True)
class ToolCallEvent:
    tool: str
    args: dict | str | None = None
    tool_id: str | None = None


@dataclass(frozen=True)
class ToolResultEvent:
    tool: str
    output: str = ""
    exit_code: int | None = None
    duration_ms: float | None = None


@dataclass(frozen=True)
class UsageEvent:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


AgentEvent = ThinkingEvent | ToolCallEvent | ToolResultEvent | UsageEvent


@dataclass(frozen=True)
class GenerationResult:
    text: str
    events: tuple[AgentEvent, ...] = ()
    session_id: str | None = None
    usage: UsageEvent | None = None
    returncode: int = 0


@dataclass
class SessionInfo:
    session_id: str | None = None


@dataclass(frozen=True)
class CommandSpec:
    argv: list[str]
    stdin: str
    cwd: str | None = None
    env: dict[str, str] | None = None
    timeout: float = 300.0
