from __future__ import annotations

import asyncio
import os
import re
import signal
from typing import TYPE_CHECKING

from ._types import CommandSpec

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Matches ANSI/VT100 escape sequences (colour, cursor movement, etc.) that
# agent CLIs emit for a human terminal. Left in place, they show up as raw
# "\x1b[91m" garbage in an HTTP error body or a log line, since neither
# renders escape codes. This is the one seam all subprocess output passes
# through, so stripping happens here rather than at each call site.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


class AgentProcessError(RuntimeError):
    def __init__(self, returncode: int, stderr: str, argv: list[str]) -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.argv = argv
        snippet = stderr.strip().split("\n")[-1] if stderr.strip() else "no stderr output"
        super().__init__(f"Agent process exited with code {returncode}: {snippet}")


class ProviderOutputError(RuntimeError):
    """A provider CLI reported a failure while still exiting successfully.

    aider prints litellm's error to stdout and exits 0, so nothing downstream
    could tell the difference between an answer and an error, and the error
    text was handed back as the assistant's reply.
    """

    def __init__(self, message: str, argv: list[str] | None = None) -> None:
        self.argv = argv or []
        super().__init__(message)


class AsyncSubprocessExecutor:
    async def run_streaming(
        self,
        spec: CommandSpec,
    ) -> AsyncIterator[tuple[str, str]]:
        process = await asyncio.create_subprocess_exec(
            *spec.argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=spec.cwd,
            env=spec.env or os.environ,
            start_new_session=True,
        )

        if process.stdin is not None:
            if spec.stdin:
                process.stdin.write(spec.stdin.encode())
                await process.stdin.drain()
            process.stdin.close()

        assert process.stdout is not None
        assert process.stderr is not None

        stderr_lines: list[str] = []

        try:
            async with asyncio.timeout(spec.timeout):

                async def forward_stderr() -> None:
                    async for line in process.stderr:
                        decoded = line.decode() if isinstance(line, bytes) else line
                        stderr_lines.append(_strip_ansi(decoded))

                stderr_task = asyncio.create_task(forward_stderr())

                async for line in process.stdout:
                    decoded = line.decode() if isinstance(line, bytes) else line
                    yield ("stdout", _strip_ansi(decoded))

                await stderr_task
                await process.wait()
        except TimeoutError:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            await process.wait()
            raise AgentProcessError(-1, "Timeout exceeded", spec.argv) from None
        except BaseException:
            try:
                if process.returncode is None:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            await process.wait()
            raise

        if process.returncode != 0:
            raise AgentProcessError(
                process.returncode or 1,
                "".join(stderr_lines),
                spec.argv,
            )

        for line in stderr_lines:
            yield ("stderr", line)

    async def run(self, spec: CommandSpec) -> tuple[str, str]:
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        async for stream, line in self.run_streaming(spec):
            if stream == "stdout":
                stdout_chunks.append(line)
            else:
                stderr_chunks.append(line)
        return "".join(stdout_chunks), "".join(stderr_chunks)

    async def check_binary(self, binary_name: str, env: dict[str, str] | None = None) -> str:
        import shutil

        binary_path = shutil.which(binary_name, path=(env or os.environ).get("PATH"))
        if not binary_path:
            binary_path = shutil.which(binary_name)
        if not binary_path:
            raise RuntimeError(f"{binary_name} binary not found in PATH")

        spec = CommandSpec(
            argv=[binary_path, "--help"],
            stdin="",
            env=env,
            timeout=15.0,
        )
        try:
            await self.run(spec)
        except AgentProcessError:
            pass
        except Exception as e:
            raise RuntimeError(f"{binary_name} CLI check failed: {e}") from e

        return binary_path
