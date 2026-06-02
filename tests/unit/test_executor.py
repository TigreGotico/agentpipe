"""Tests for agentpipe._executor — AsyncSubprocessExecutor."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, patch

import pytest

from agentpipe._executor import AgentProcessError, AsyncSubprocessExecutor
from agentpipe._types import CommandSpec

_needs_311 = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="asyncio.timeout requires Python 3.11+",
)


class TestAgentProcessError:
    def test_message_from_stderr(self):
        err = AgentProcessError(1, "first\nsecond\nlast line", ["cmd"])
        assert "last line" in str(err)
        assert err.returncode == 1
        assert err.stderr == "first\nsecond\nlast line"
        assert err.argv == ["cmd"]

    def test_empty_stderr(self):
        err = AgentProcessError(2, "", ["cmd"])
        assert "no stderr output" in str(err)

    def test_whitespace_only_stderr(self):
        err = AgentProcessError(1, "   \n  ", ["cmd"])
        assert "no stderr output" in str(err)

    def test_repr(self):
        err = AgentProcessError(1, "err", ["echo"])
        assert "1" in str(err)


def _make_spec(**overrides) -> CommandSpec:
    defaults = {"argv": ["echo", "hi"], "stdin": "", "timeout": 5.0}
    defaults.update(overrides)
    return CommandSpec(**defaults)


class TestAsyncSubprocessExecutorRun:
    @pytest.mark.asyncio
    async def test_run_collects_stdout_and_stderr(self):
        executor = AsyncSubprocessExecutor()

        async def mock_streaming(spec):
            yield ("stdout", "hello\n")
            yield ("stdout", "world\n")
            yield ("stderr", "warn\n")

        executor.run_streaming = mock_streaming
        stdout, stderr = await executor.run(_make_spec())
        assert "hello" in stdout
        assert "world" in stdout
        assert "warn" in stderr

    @pytest.mark.asyncio
    async def test_run_raises_on_streaming_error(self):
        executor = AsyncSubprocessExecutor()

        async def mock_streaming(spec):
            raise AgentProcessError(1, "fatal error", ["cmd"])
            yield

        executor.run_streaming = mock_streaming
        with pytest.raises(AgentProcessError) as exc_info:
            await executor.run(_make_spec())
        assert exc_info.value.returncode == 1

    @pytest.mark.asyncio
    async def test_run_empty_output(self):
        executor = AsyncSubprocessExecutor()

        async def mock_streaming(spec):
            return
            yield

        executor.run_streaming = mock_streaming
        stdout, stderr = await executor.run(_make_spec())
        assert stdout == ""
        assert stderr == ""


class TestAsyncSubprocessExecutorRunStreaming:
    @_needs_311
    @pytest.mark.asyncio
    async def test_streaming_success(self):
        executor = AsyncSubprocessExecutor()
        spec = CommandSpec(argv=["echo", "hello"], stdin="", timeout=5.0)

        results = []
        async for stream, line in executor.run_streaming(spec):
            results.append((stream, line))

        assert len(results) > 0
        stdout_lines = [line for s, line in results if s == "stdout"]
        assert any("hello" in line for line in stdout_lines)

    @_needs_311
    @pytest.mark.asyncio
    async def test_streaming_nonzero_exit(self):
        executor = AsyncSubprocessExecutor()
        spec = CommandSpec(argv=["sh", "-c", "echo err >&2; exit 1"], stdin="", timeout=5.0)

        with pytest.raises(AgentProcessError) as exc_info:
            async for _ in executor.run_streaming(spec):
                pass
        assert exc_info.value.returncode == 1
        assert "err" in exc_info.value.stderr

    @_needs_311
    @pytest.mark.asyncio
    async def test_streaming_without_stdin(self):
        executor = AsyncSubprocessExecutor()
        spec = CommandSpec(argv=["echo", "no stdin"], stdin="", timeout=5.0)

        results = []
        async for stream, line in executor.run_streaming(spec):
            results.append((stream, line))

        stdout = "".join(line for s, line in results if s == "stdout")
        assert "no stdin" in stdout

    @_needs_311
    @pytest.mark.asyncio
    async def test_streaming_timeout(self):
        executor = AsyncSubprocessExecutor()
        spec = CommandSpec(argv=["sleep", "30"], stdin="", timeout=0.1)

        with pytest.raises(AgentProcessError) as exc_info:
            async for _ in executor.run_streaming(spec):
                pass
        assert exc_info.value.returncode == -1
        assert "Timeout" in exc_info.value.stderr


class TestAsyncSubprocessExecutorCheckBinary:
    @_needs_311
    @pytest.mark.asyncio
    async def test_check_binary_found(self):
        executor = AsyncSubprocessExecutor()
        result = await executor.check_binary("echo")
        assert "echo" in result

    @pytest.mark.asyncio
    async def test_check_binary_not_found(self):
        executor = AsyncSubprocessExecutor()
        with pytest.raises(RuntimeError, match="not found in PATH"):
            await executor.check_binary("nonexistent_binary_name_xyz_123")

    @pytest.mark.asyncio
    async def test_check_binary_help_fails_gracefully(self):
        executor = AsyncSubprocessExecutor()
        executor.run = AsyncMock(side_effect=AgentProcessError(1, "err", ["tool"]))
        with patch("shutil.which", return_value="/usr/bin/tool"):
            result = await executor.check_binary("tool")
            assert result == "/usr/bin/tool"

    @pytest.mark.asyncio
    async def test_check_binary_non_process_error_raises(self):
        executor = AsyncSubprocessExecutor()
        executor.run = AsyncMock(side_effect=OSError("broken"))
        with patch("shutil.which", return_value="/usr/bin/tool"):
            with pytest.raises(RuntimeError, match="CLI check failed"):
                await executor.check_binary("tool")
