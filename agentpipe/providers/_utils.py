"""Shared utilities for provider implementations.

Extracted from duplicated patterns across claude, gemini, kilo, opencode,
qoder, and vibe providers.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import TYPE_CHECKING, Any

from .._types import HttpMcpServer, StdioMcpServer, ToolResultEvent, UsageEvent

if TYPE_CHECKING:
    from .._types import McpServerConfig

# ── effort → variant mapping (shared by opencode & kilo) ──────────────
EFFORT_VARIANT_MAP: dict[str, str] = {
    "low": "minimal",
    "medium": "low",
    "high": "high",
    "xhigh": "max",
    "max": "max",
}


# ── MCP config JSON builder (shared by claude & qoder) ────────────────
def build_mcp_config_json(servers: list[McpServerConfig]) -> str:
    out: dict[str, dict[str, Any]] = {}
    for server in servers:
        if isinstance(server, HttpMcpServer):
            entry: dict[str, Any] = {"type": "sse", "url": server.url}
            if server.headers:
                entry["headers"] = dict(server.headers)
            out[server.name] = entry
        else:
            stdio_entry: dict[str, Any] = {"command": server.command, "args": server.args}
            if isinstance(server, StdioMcpServer) and server.env:
                stdio_entry["env"] = server.env
            out[server.name] = stdio_entry
    return json.dumps({"mcpServers": out})


# ── default build_env (shared by kilo, opencode, vibe, qoder) ─────────
def default_build_env() -> dict[str, str]:
    return dict(os.environ)


# ── tool-call tracking (shared by claude, gemini, qoder, vibe) ─────────
class ToolTracker:
    """Track tool ID → name mapping and per-tool timing."""

    __slots__ = ("_map", "_starts", "_lock")

    def __init__(self, *, thread_safe: bool = False) -> None:
        self._map: dict[str, str] = {}
        self._starts: dict[str, float] = {}
        self._lock: threading.Lock | None = threading.Lock() if thread_safe else None

    def record(self, tool_id: str, tool_name: str) -> None:
        now = time.monotonic()
        if self._lock:
            with self._lock:
                self._map[tool_id] = tool_name
                self._starts[tool_id] = now
        else:
            self._map[tool_id] = tool_name
            self._starts[tool_id] = now

    def resolve(self, tool_id: str | None) -> ToolResultEvent:
        """Look up tool name and compute duration for a tool result.

        Returns a partially-filled ToolResultEvent (caller sets ``output``).
        """
        key = tool_id or ""
        if self._lock:
            with self._lock:
                name = self._map.get(key, "Tool")
                start = self._starts.get(key)
        else:
            name = self._map.get(key, "Tool")
            start = self._starts.get(key)
        duration_ms = ((time.monotonic() - start) * 1000) if start else None
        return ToolResultEvent(tool=name, duration_ms=duration_ms)


# ── session-ID extraction from raw JSON lines ─────────────────────────
def extract_session_id_from_json(
    raw_lines: list[str],
    *,
    keys: tuple[str, ...] = ("session_id", "sessionID"),
) -> str | None:
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            continue
        for key in keys:
            sid = data.get(key)
            if isinstance(sid, str) and sid:
                return sid
    return None


# ── UsageEvent from opencode/kilo step_finish tokens dict ─────────────
def usage_from_step_finish(tokens: dict[str, Any], cost: float | None = None) -> UsageEvent:
    cache = tokens.get("cache") or {}
    cache_read = int(cache.get("read") or 0)
    cache_write = int(cache.get("write") or 0)
    cached = cache_read + cache_write
    return UsageEvent(
        input_tokens=int(tokens.get("input") or 0) + cached,
        output_tokens=int(tokens.get("output") or 0) + int(tokens.get("reasoning") or 0),
        cost_usd=cost,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )


# ── UsageEvent from Anthropic-style usage dict (claude / qoder) ───────
def usage_from_anthropic(usage: dict[str, Any], cost_usd: float | None = None) -> UsageEvent:
    cached = int(usage.get("cache_creation_input_tokens") or 0) + int(usage.get("cache_read_input_tokens") or 0)
    return UsageEvent(
        input_tokens=int(usage.get("input_tokens") or 0) + cached,
        output_tokens=int(usage.get("output_tokens") or 0),
        cost_usd=cost_usd,
        cache_read_tokens=int(usage.get("cache_read_input_tokens") or 0),
        cache_write_tokens=int(usage.get("cache_creation_input_tokens") or 0),
    )
