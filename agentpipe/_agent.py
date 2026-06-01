from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ._executor import AgentProcessError, AsyncSubprocessExecutor
from ._session import AgentSession
from ._types import (
    ApprovalMode,
    AuthStatus,
    McpServerConfig,
    ModelInfo,
    SessionEntry,
)
from .providers.claude import ClaudeHaikuProvider, ClaudeOpusProvider, ClaudeProvider, ClaudeSonnetProvider
from .providers.gemini import GeminiFlashProvider, GeminiProProvider, GeminiProvider
from .providers.opencode import (
    OpencodeFreeProvider,
    OpencodeGoProvider,
    OpencodeZenProvider,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ._types import AgentEvent, GenerationResult, Provider

DEFAULT_CWD = "/tmp"

DEFAULT_MODELS: dict[str, str] = {
    "claude": "sonnet",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
    "claude-opus": "opus",
    "gemini": "gemini-2.5-flash",
    "gemini-flash": "gemini-2.5-flash",
    "gemini-pro": "gemini-2.5-pro",
    "opencode": "opencode/gemini-3-flash",
    "opencode-free": "opencode/big-pickle",
    "opencode-zen": "opencode/gemini-3-flash",
    "opencode-go": "opencode-go/deepseek-v4-flash",
}

_PROVIDER_MAP: dict[str, type] = {
    "claude": ClaudeProvider,
    "claude-sonnet": ClaudeSonnetProvider,
    "claude-haiku": ClaudeHaikuProvider,
    "claude-opus": ClaudeOpusProvider,
    "gemini": GeminiProvider,
    "gemini-flash": GeminiFlashProvider,
    "gemini-pro": GeminiProProvider,
    "opencode": OpencodeZenProvider,
    "opencode-free": OpencodeFreeProvider,
    "opencode-zen": OpencodeZenProvider,
    "opencode-go": OpencodeGoProvider,
}


def _resolve_provider(name: str, model: str | None = None) -> Provider:
    cls = _PROVIDER_MAP.get(name)
    if cls is None:
        available = ", ".join(sorted(_PROVIDER_MAP.keys()))
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")
    return cls(model=model)


@dataclass
class Agent:
    provider: str
    model: str | None = None
    cwd: str = field(default_factory=lambda: DEFAULT_CWD)
    timeout: int = 300
    mcp_servers: list[McpServerConfig] = field(default_factory=list)
    approval_mode: ApprovalMode | None = None
    max_budget_usd: float | None = None
    executor: AsyncSubprocessExecutor = field(default_factory=AsyncSubprocessExecutor)

    def __post_init__(self) -> None:
        if self.model is None:
            self.model = DEFAULT_MODELS.get(self.provider)
        cls = _PROVIDER_MAP.get(self.provider)
        if cls is None:
            available = ", ".join(sorted(_PROVIDER_MAP.keys()))
            raise ValueError(f"Unknown provider '{self.provider}'. Available: {available}")
        kwargs: dict = {"model": self.model}
        if self.mcp_servers:
            kwargs["mcp_servers"] = self.mcp_servers
        if self.approval_mode is not None:
            kwargs["approval_mode"] = self.approval_mode
        if self.max_budget_usd is not None:
            kwargs["max_budget_usd"] = self.max_budget_usd
        self._provider_instance = cls(**kwargs)

    async def generate(
        self,
        prompt: str,
        *,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> str:
        async with self.session(cwd=cwd, timeout=timeout) as session:
            return await session.generate(prompt)

    async def generate_stream(
        self,
        prompt: str,
        *,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> AsyncIterator[AgentEvent]:
        session = self.session(cwd=cwd, timeout=timeout)
        return session.generate_stream(prompt)

    async def generate_full(
        self,
        prompt: str,
        *,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> GenerationResult:
        async with self.session(cwd=cwd, timeout=timeout) as session:
            return await session.generate_full(prompt)

    def session(
        self,
        *,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> AgentSession:
        effective_cwd = cwd or self.cwd
        effective_timeout = timeout or self.timeout
        return AgentSession(
            self._provider_instance,
            cwd=effective_cwd,
            timeout=effective_timeout,
            executor=self.executor,
        )

    async def check_available(self) -> str:
        return await self.executor.check_binary(self._provider_instance.binary_name)

    async def auth_status(self) -> AuthStatus:
        if self.provider == "claude":
            return await self._claude_auth_status()
        if self.provider == "gemini":
            return await self._gemini_auth_status()
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_auth_status()
        return AuthStatus(authenticated=False, provider=self.provider)

    async def list_sessions(self, *, cwd: str | None = None) -> list[SessionEntry]:
        effective_cwd = cwd or self.cwd
        if self.provider == "gemini":
            return await self._gemini_list_sessions(effective_cwd)
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_list_sessions(effective_cwd)
        raise NotImplementedError(f"list_sessions not supported for {self.provider}")

    async def list_models(self) -> list[ModelInfo]:
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_list_models()
        raise NotImplementedError(f"list_models not supported for {self.provider}")

    async def stats(self, *, days: int | None = None, cwd: str | None = None) -> dict:
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_stats(days=days, cwd=cwd or self.cwd)
        raise NotImplementedError(f"stats not supported for {self.provider}")

    async def _claude_auth_status(self) -> AuthStatus:
        from ._types import CommandSpec

        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "auth", "status", "--json"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            data = json.loads(stdout)
            return AuthStatus(
                authenticated=data.get("loggedIn", False),
                provider="claude",
                email=data.get("email"),
                method=data.get("authMethod"),
                subscription_type=data.get("subscriptionType"),
                raw=data,
            )
        except (AgentProcessError, json.JSONDecodeError):
            return AuthStatus(authenticated=False, provider="claude")

    async def _gemini_auth_status(self) -> AuthStatus:
        from ._types import CommandSpec

        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "--version"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=10.0,
        )
        try:
            await self.executor.run(spec)
            return AuthStatus(authenticated=True, provider="gemini")
        except AgentProcessError:
            return AuthStatus(authenticated=False, provider="gemini")

    async def _opencode_auth_status(self) -> AuthStatus:
        from ._types import CommandSpec

        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "providers", "list"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            has_any = len(stdout.strip()) > 0
            return AuthStatus(authenticated=has_any, provider="opencode", raw=None)
        except AgentProcessError:
            return AuthStatus(authenticated=False, provider="opencode")

    async def _gemini_list_sessions(self, cwd: str) -> list[SessionEntry]:
        from ._types import CommandSpec

        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "--list-sessions"],
            stdin="",
            cwd=cwd,
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            entries: list[SessionEntry] = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                if line:
                    entries.append(SessionEntry(session_id=line, provider="gemini"))
            return entries
        except AgentProcessError:
            return []

    async def _opencode_list_sessions(self, cwd: str) -> list[SessionEntry]:
        from ._types import CommandSpec

        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "session", "list"],
            stdin="",
            cwd=cwd,
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            entries: list[SessionEntry] = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                if line:
                    entries.append(SessionEntry(session_id=line, provider="opencode"))
            return entries
        except AgentProcessError:
            return []

    async def _opencode_list_models(self) -> list[ModelInfo]:
        from ._types import CommandSpec

        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "models"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=30.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            models: list[ModelInfo] = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                if line:
                    models.append(ModelInfo(id=line, provider="opencode"))
            return models
        except AgentProcessError:
            return []

    async def _opencode_stats(self, *, days: int | None = None, cwd: str) -> dict:
        from ._types import CommandSpec

        cmd = [self._provider_instance.binary_name, "stats"]
        if days is not None:
            cmd.extend(["--days", str(days)])
        spec = CommandSpec(
            argv=cmd,
            stdin="",
            cwd=cwd,
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            return {"raw": stdout}
        except AgentProcessError:
            return {"raw": ""}
