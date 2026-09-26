from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .._types import AgentEvent


class Provider(Protocol):
    @property
    def binary_name(self) -> str: ...

    @property
    def model(self) -> str | None: ...

    def build_command(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        model: str | None = None,
    ) -> list[str]: ...

    def parse_event_line(self, line: str) -> list[AgentEvent]: ...

    def extract_session_id(self, raw_lines: list[str]) -> str | None: ...

    def extract_text(self, raw_lines: list[str]) -> str: ...

    def detect_error(self, raw_lines: list[str]) -> str | None:
        """Name the failure this output reports, or None if it reports none.

        A CLI that fails while exiting 0 is invisible to the exit code, and
        its error text otherwise reaches the caller as an answer.
        """
        ...

    def build_env(self) -> dict[str, str]: ...
