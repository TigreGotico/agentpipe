"""Client-caused mistakes on /v1/chat/completions must come back as 4xx, not
500, so a caller can tell "you sent something wrong" from "the server broke".
A provider CLI that is not installed is a server-side configuration problem,
not the caller's fault, so it gets 503 with a message naming the CLI.
"""
import sys
import importlib

import pytest

pytest.importorskip("fastapi")

from fastapi import HTTPException


def _load_server(monkeypatch, no_path=False):
    for key in ("AGENTPIPE_STATELESS", "AGENTPIPE_OPENAI_APPROVAL",
                "AGENTPIPE_MAX_CONCURRENCY", "AGENTPIPE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    if no_path:
        # No CLI binary is reachable, so a validation error (400) is what
        # must stop these requests before any subprocess is ever attempted;
        # otherwise the test would hang waiting on a real agent CLI.
        monkeypatch.setenv("PATH", "/nonexistent-agentpipe-test-path")
    sys.modules.pop("agentpipe.server", None)
    return importlib.import_module("agentpipe.server")


class TestMissingModelIsRejected:
    async def test_omitting_model_is_a_validation_error_not_a_silent_default(self, monkeypatch):
        server = _load_server(monkeypatch, no_path=True)
        body = {"messages": [{"role": "user", "content": "hi"}]}
        with pytest.raises(HTTPException) as exc_info:
            await server.openai_chat_completions(body)
        assert exc_info.value.status_code == 400


class TestEmptyMessagesIsRejected:
    async def test_empty_messages_list_is_a_client_error(self, monkeypatch):
        server = _load_server(monkeypatch, no_path=True)
        body = {"model": "opencode/deepseek-v4-flash-free", "messages": []}
        with pytest.raises(HTTPException) as exc_info:
            await server.openai_chat_completions(body)
        assert exc_info.value.status_code == 400


class TestUnavailableProviderCliIs503:
    async def test_missing_cli_binary_is_503_naming_the_cli(self, monkeypatch):
        server = _load_server(monkeypatch, no_path=True)
        body = {
            "model": "opencode/deepseek-v4-flash-free",
            "messages": [{"role": "user", "content": "hi"}],
        }
        with pytest.raises(HTTPException) as exc_info:
            await server.openai_chat_completions(body)
        assert exc_info.value.status_code == 503
        assert "opencode" in exc_info.value.detail
