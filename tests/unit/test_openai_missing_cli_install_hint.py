"""A missing provider CLI is a server-side configuration problem the operator
can fix, so the 503 should name the CLI and say how to install it -- not just
report that it is missing.
"""
import sys
import importlib

import pytest

pytest.importorskip("fastapi")

from fastapi import HTTPException


def _load_server(monkeypatch):
    for key in ("AGENTPIPE_STATELESS", "AGENTPIPE_OPENAI_APPROVAL",
                "AGENTPIPE_MAX_CONCURRENCY", "AGENTPIPE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PATH", "/nonexistent-agentpipe-test-path")
    sys.modules.pop("agentpipe.server", None)
    return importlib.import_module("agentpipe.server")


class TestMissingCliMessageNamesTheInstallCommand:
    async def test_503_includes_how_to_install_opencode(self, monkeypatch):
        server = _load_server(monkeypatch)
        body = {
            "model": "opencode/deepseek-v4-flash-free",
            "messages": [{"role": "user", "content": "hi"}],
        }
        with pytest.raises(HTTPException) as exc_info:
            await server.openai_chat_completions(body)
        assert exc_info.value.status_code == 503
        assert "opencode" in exc_info.value.detail
        assert "npm install -g opencode" in exc_info.value.detail

    async def test_503_includes_how_to_install_aider(self, monkeypatch):
        server = _load_server(monkeypatch)
        body = {
            "model": "aider",
            "messages": [{"role": "user", "content": "hi"}],
        }
        with pytest.raises(HTTPException) as exc_info:
            await server.openai_chat_completions(body)
        assert exc_info.value.status_code == 503
        assert "pip install aider-chat" in exc_info.value.detail
