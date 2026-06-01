from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ._executor import AsyncSubprocessExecutor
from ._session import AgentSession
from .providers.claude import ClaudeProvider
from .providers.gemini import GeminiProvider
from .providers.opencode import OpencodeProvider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ._types import AgentEvent, GenerationResult, Provider

DEFAULT_CWD = "/tmp"

DEFAULT_MODELS: dict[str, str] = {
    "claude": "sonnet",
    "gemini": "gemini-2.5-flash",
    "opencode": "opencode/gemini-3-flash",
}

_PROVIDER_MAP: dict[str, type] = {
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
    "opencode": OpencodeProvider,
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
    executor: AsyncSubprocessExecutor = field(default_factory=AsyncSubprocessExecutor)

    def __post_init__(self) -> None:
        if self.model is None:
            self.model = DEFAULT_MODELS.get(self.provider)
        cls = _PROVIDER_MAP.get(self.provider)
        if cls is None:
            available = ", ".join(sorted(_PROVIDER_MAP.keys()))
            raise ValueError(f"Unknown provider '{self.provider}'. Available: {available}")
        self._provider_instance = cls(model=self.model)

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
