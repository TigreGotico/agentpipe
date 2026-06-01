from __future__ import annotations

from typing import TYPE_CHECKING

from ._executor import AsyncSubprocessExecutor
from ._types import CommandSpec, GenerationResult, SessionInfo, UsageEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ._types import AgentEvent
    from .providers._base import Provider


class AgentSession:
    def __init__(
        self,
        provider: Provider,
        *,
        cwd: str | None = None,
        timeout: int = 300,
        executor: AsyncSubprocessExecutor | None = None,
    ) -> None:
        self._provider = provider
        self._cwd = cwd
        self._timeout = timeout
        self._executor = executor or AsyncSubprocessExecutor()
        self._info = SessionInfo()

    async def __aenter__(self) -> AgentSession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        pass

    @property
    def session_id(self) -> str | None:
        return self._info.session_id

    async def generate(self, prompt: str, *, cwd: str | None = None, timeout: int | None = None) -> str:
        result = await self.generate_full(prompt, cwd=cwd, timeout=timeout)
        return result.text

    async def generate_stream(
        self,
        prompt: str,
        *,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> AsyncIterator[AgentEvent]:
        effective_cwd = cwd or self._cwd
        effective_timeout = timeout if timeout is not None else self._timeout

        cmd = self._provider.build_command(
            prompt,
            session_id=self._info.session_id,
        )
        spec = CommandSpec(
            argv=cmd,
            stdin="",
            cwd=effective_cwd,
            env=self._provider.build_env(),
            timeout=float(effective_timeout),
        )

        raw_lines: list[str] = []
        session_id_collected: str | None = None

        async for stream, line in self._executor.run_streaming(spec):
            if stream == "stdout":
                raw_lines.append(line)
                stripped = line.strip()
                if stripped:
                    if session_id_collected is None:
                        sid = self._provider.extract_session_id([line])
                        if sid:
                            session_id_collected = sid
                    for event in self._provider.parse_event_line(stripped):
                        yield event

        if self._info.session_id is None and session_id_collected:
            self._info.session_id = session_id_collected
        if self._info.session_id is None:
            sid = self._provider.extract_session_id(raw_lines)
            if sid:
                self._info.session_id = sid

    async def generate_full(
        self,
        prompt: str,
        *,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> GenerationResult:
        effective_cwd = cwd or self._cwd
        effective_timeout = timeout if timeout is not None else self._timeout

        cmd = self._provider.build_command(
            prompt,
            session_id=self._info.session_id,
        )
        spec = CommandSpec(
            argv=cmd,
            stdin="",
            cwd=effective_cwd,
            env=self._provider.build_env(),
            timeout=float(effective_timeout),
        )

        stdout, _stderr = await self._executor.run(spec)

        raw_lines = stdout.splitlines(keepends=True)
        session_id: str | None = self._provider.extract_session_id(raw_lines)
        if self._info.session_id is None and session_id:
            self._info.session_id = session_id

        text = self._provider.extract_text(raw_lines)

        events: list[AgentEvent] = []
        last_usage: UsageEvent | None = None
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            for event in self._provider.parse_event_line(stripped):
                events.append(event)
                if isinstance(event, UsageEvent):
                    last_usage = event

        return GenerationResult(
            text=text,
            events=tuple(events),
            session_id=self._info.session_id,
            usage=last_usage,
            returncode=0,
        )
