from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Provider(str, Enum):
    CLAUDE = "claude"
    GEMINI = "gemini"
    OPENCODE = "opencode"


class ApprovalMode(str, Enum):
    DEFAULT = "default"
    AUTO_EDIT = "auto_edit"
    YOLO = "yolo"
    PLAN = "plan"
    BYPASS = "bypass"


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


@dataclass
class SessionUsage:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_cache_read_tokens: int = 0
    total_cache_write_tokens: int = 0
    turn_count: int = 0

    def add(self, usage: UsageEvent) -> None:
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        if usage.cost_usd is not None:
            self.total_cost_usd += usage.cost_usd
        self.total_cache_read_tokens += usage.cache_read_tokens
        self.total_cache_write_tokens += usage.cache_write_tokens
        self.turn_count += 1


@dataclass(frozen=True)
class HttpMcpServer:
    name: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StdioMcpServer:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


McpServerConfig = HttpMcpServer | StdioMcpServer


@dataclass(frozen=True)
class AuthStatus:
    authenticated: bool
    provider: str
    email: str | None = None
    method: str | None = None
    subscription_type: str | None = None
    raw: dict | None = None


@dataclass(frozen=True)
class SessionEntry:
    session_id: str
    title: str | None = None
    created_at: str | None = None
    provider: str | None = None


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str | None = None
    provider: str | None = None
    context_window: int | None = None
    cost_per_million_input: float | None = None
    cost_per_million_output: float | None = None
