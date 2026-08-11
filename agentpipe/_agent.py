from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ._executor import AgentProcessError, AsyncSubprocessExecutor
from ._session import AgentSession
from ._types import (
    ApprovalMode,
    AuthStatus,
    CommandSpec,
    EffortLevel,
    ExtensionInfo,
    McpServerConfig,
    McpServerInfo,
    ModelInfo,
    SessionEntry,
    SessionExport,
)
from .providers.aider import AiderProvider
from .providers.antigravity import (
    AntigravityClaudeOpusProvider,
    AntigravityClaudeSonnetProvider,
    AntigravityFlashHighProvider,
    AntigravityFlashLowProvider,
    AntigravityFlashMediumProvider,
    AntigravityGptOssProvider,
    AntigravityProHighProvider,
    AntigravityProLowProvider,
    AntigravityProvider,
)
from .providers.claude import ClaudeHaikuProvider, ClaudeOpusProvider, ClaudeProvider, ClaudeSonnetProvider
from .providers.gemini import GeminiFlashProvider, GeminiProProvider, GeminiProvider
from .providers.kilo import KiloProvider
from .providers.mimocode import (
    MimocodeAutoProvider,
    MimocodeProvider,
    MimocodeV2FlashProvider,
    MimocodeV2ProProvider,
)
from .providers.opencode import (
    OpencodeFreeProvider,
    OpencodeGoProvider,
    OpencodeZenProvider,
)
from .providers.qoder import QoderProvider
from .providers.vibe import VibeProvider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ._types import AgentEvent, GenerationResult, Provider

logger = logging.getLogger(__name__)

DEFAULT_CWD = os.environ.get("AGENTPIPE_CWD", "/tmp")

DEFAULT_MODELS: dict[str, str] = {
    "aider": "openrouter/google/gemma-4-26b-a4b-it:free",
    "claude": "sonnet",
    "kilo": "kilo/kilo-auto/free",
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
    "mimo": "mimo/mimo-auto",
    "mimo-auto": "mimo/mimo-auto",
    "mimo-v2-pro": "xiaomi/mimo-v2.5-pro",
    "mimo-v2-flash": "xiaomi/mimo-v2-flash",
    "qoder": "mistral-large-latest",
    "vibe": "mistral-large-latest",
    "antigravity": "Gemini 3.5 Flash (Medium)",
    "antigravity-flash-medium": "Gemini 3.5 Flash (Medium)",
    "antigravity-flash-high": "Gemini 3.5 Flash (High)",
    "antigravity-flash-low": "Gemini 3.5 Flash (Low)",
    "antigravity-pro-low": "Gemini 3.1 Pro (Low)",
    "antigravity-pro-high": "Gemini 3.1 Pro (High)",
    "antigravity-claude-sonnet": "Claude Sonnet 4.6 (Thinking)",
    "antigravity-claude-opus": "Claude Opus 4.6 (Thinking)",
    "antigravity-gpt-oss": "GPT-OSS 120B (Medium)",
}

_PROVIDER_MAP: dict[str, type] = {
    "aider": AiderProvider,
    "claude": ClaudeProvider,
    "kilo": KiloProvider,
    "mimo": MimocodeProvider,
    "mimo-auto": MimocodeAutoProvider,
    "mimo-v2-pro": MimocodeV2ProProvider,
    "mimo-v2-flash": MimocodeV2FlashProvider,
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
    "qoder": QoderProvider,
    "vibe": VibeProvider,
    "antigravity": AntigravityProvider,
    "antigravity-flash-medium": AntigravityFlashMediumProvider,
    "antigravity-flash-high": AntigravityFlashHighProvider,
    "antigravity-flash-low": AntigravityFlashLowProvider,
    "antigravity-pro-low": AntigravityProLowProvider,
    "antigravity-pro-high": AntigravityProHighProvider,
    "antigravity-claude-sonnet": AntigravityClaudeSonnetProvider,
    "antigravity-claude-opus": AntigravityClaudeOpusProvider,
    "antigravity-gpt-oss": AntigravityGptOssProvider,
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

    # Module 1: Tool allow/deny + system prompt
    system_prompt: str | None = None
    append_system_prompt: str | None = None
    allowed_tools: list[str] | None = None
    disallowed_tools: list[str] | None = None

    # Module 2: Effort level + structured output + fallback
    effort: EffortLevel | None = None
    fallback_model: str | None = None
    json_schema: dict | None = None

    # Module 3: Session lifecycle
    session_name: str | None = None
    continue_last: bool = False
    fork_session: bool = False

    # Module 6: File attachments
    files: list[str] | None = None

    # Module 7: Agent selection
    agent_name: str | None = None

    # Module 9: Sandbox and output control
    sandbox: bool = False
    raw_output: bool = False
    include_dirs: list[str] | None = None

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
        if self.system_prompt is not None:
            kwargs["system_prompt"] = self.system_prompt
        if self.append_system_prompt is not None:
            kwargs["append_system_prompt"] = self.append_system_prompt
        if self.allowed_tools is not None:
            kwargs["allowed_tools"] = self.allowed_tools
        if self.disallowed_tools is not None:
            kwargs["disallowed_tools"] = self.disallowed_tools
        if self.effort is not None:
            kwargs["effort"] = self.effort.value
        if self.fallback_model is not None:
            kwargs["fallback_model"] = self.fallback_model
        if self.json_schema is not None:
            kwargs["json_schema"] = self.json_schema
        if self.session_name is not None:
            kwargs["session_name"] = self.session_name
        if self.agent_name is not None:
            kwargs["agent_name"] = self.agent_name
        if self.sandbox:
            kwargs["sandbox"] = self.sandbox
        if self.raw_output:
            kwargs["raw_output"] = self.raw_output
        if self.include_dirs is not None:
            kwargs["include_dirs"] = self.include_dirs
        if self.continue_last:
            kwargs["continue_last"] = self.continue_last
        if self.fork_session:
            kwargs["fork_session"] = self.fork_session
        if self.files is not None:
            kwargs["files"] = self.files
        self._provider_instance = cls(**kwargs)

    # Fields the provider copies at construction. Setting one on a built Agent
    # has to be pushed through, or the assignment is silently discarded.
    _PROVIDER_SYNCED = ("continue_last", "fork_session")

    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        if name in Agent._PROVIDER_SYNCED:
            provider = self.__dict__.get("_provider_instance")
            if provider is not None:
                setattr(provider, f"_{name}", value)

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
        async with self.session(cwd=cwd, timeout=timeout) as session:
            async for event in session.generate_stream(prompt):
                yield event

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
        if self.provider.startswith("antigravity"):
            return await self._antigravity_auth_status()
        if self.provider == "claude":
            return await self._claude_auth_status()
        if self.provider == "gemini":
            return await self._gemini_auth_status()
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_auth_status()
        if self.provider in ("mimo", "mimo-auto", "mimo-v2-pro", "mimo-v2-flash"):
            return await self._mimo_auth_status()
        return AuthStatus(authenticated=False, provider=self.provider)

    async def auth_login(self, *, method: str | None = None) -> AuthStatus:
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_auth_login()
        if self.provider == "claude":
            return await self._claude_auth_login(method=method)
        if self.provider in ("mimo", "mimo-auto", "mimo-v2-pro", "mimo-v2-flash"):
            return await self._mimo_auth_login()
        raise NotImplementedError(f"auth_login not supported for {self.provider}")

    async def auth_logout(self) -> AuthStatus:
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_auth_logout()
        if self.provider == "claude":
            return await self._claude_auth_logout()
        if self.provider in ("mimo", "mimo-auto", "mimo-v2-pro", "mimo-v2-flash"):
            return await self._mimo_auth_logout()
        raise NotImplementedError(f"auth_logout not supported for {self.provider}")

    async def delete_session(self, session_id: str, *, cwd: str | None = None) -> bool:
        effective_cwd = cwd or self.cwd
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_delete_session(session_id, effective_cwd)
        if self.provider in ("mimo", "mimo-auto", "mimo-v2-pro", "mimo-v2-flash"):
            return await self._mimo_delete_session(session_id, effective_cwd)
        raise NotImplementedError(f"delete_session not supported for {self.provider}")

    async def export_session(self, session_id: str, *, cwd: str | None = None) -> SessionExport:
        effective_cwd = cwd or self.cwd
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_export_session(session_id, effective_cwd)
        if self.provider in ("mimo", "mimo-auto", "mimo-v2-pro", "mimo-v2-flash"):
            return await self._mimo_export_session(session_id, effective_cwd)
        raise NotImplementedError(f"export_session not supported for {self.provider}")

    async def import_session(self, data: str, *, cwd: str | None = None) -> str | None:
        effective_cwd = cwd or self.cwd
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_import_session(data, effective_cwd)
        raise NotImplementedError(f"import_session not supported for {self.provider}")

    async def mcp_add(
        self,
        name: str,
        *,
        url: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        scope: str | None = None,
    ) -> bool:
        if self.provider == "claude":
            return await self._claude_mcp_add(
                name, url=url, command=command, args=args, env=env, headers=headers, scope=scope
            )
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_mcp_add(name, url=url, command=command, args=args, env=env)
        if self.provider in ("mimo", "mimo-auto", "mimo-v2-pro", "mimo-v2-flash"):
            return await self._mimo_mcp_add(name, url=url, command=command, args=args, env=env)
        raise NotImplementedError(f"mcp_add not supported for {self.provider}")

    async def mcp_remove(self, name: str, *, scope: str | None = None) -> bool:
        if self.provider == "claude":
            return await self._claude_mcp_remove(name, scope=scope)
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_mcp_remove(name)
        if self.provider in ("mimo", "mimo-auto", "mimo-v2-pro", "mimo-v2-flash"):
            return await self._mimo_mcp_remove(name)
        raise NotImplementedError(f"mcp_remove not supported for {self.provider}")

    async def mcp_list(self) -> list[McpServerInfo]:
        if self.provider == "claude":
            return await self._claude_mcp_list()
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_mcp_list()
        if self.provider in ("mimo", "mimo-auto", "mimo-v2-pro", "mimo-v2-flash"):
            return await self._mimo_mcp_list()
        raise NotImplementedError(f"mcp_list not supported for {self.provider}")

    async def list_extensions(self) -> list[ExtensionInfo]:
        if self.provider == "gemini":
            return await self._gemini_list_extensions()
        raise NotImplementedError(f"list_extensions not supported for {self.provider}")

    async def doctor(self) -> dict:
        if self.provider == "claude":
            return await self._claude_doctor()
        raise NotImplementedError(f"doctor not supported for {self.provider}")

    async def list_sessions(self, *, cwd: str | None = None) -> list[SessionEntry]:
        effective_cwd = cwd or self.cwd
        if self.provider == "gemini":
            return await self._gemini_list_sessions(effective_cwd)
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_list_sessions(effective_cwd)
        if self.provider in ("mimo", "mimo-auto", "mimo-v2-pro", "mimo-v2-flash"):
            return await self._mimo_list_sessions(effective_cwd)
        raise NotImplementedError(f"list_sessions not supported for {self.provider}")

    async def list_models(self) -> list[ModelInfo]:
        if self.provider.startswith("antigravity"):
            return await self._antigravity_list_models()
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_list_models()
        if self.provider in ("mimo", "mimo-auto", "mimo-v2-pro", "mimo-v2-flash"):
            return await self._mimo_list_models()
        raise NotImplementedError(f"list_models not supported for {self.provider}")

    async def stats(self, *, days: int | None = None, cwd: str | None = None) -> dict:
        if self.provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
            return await self._opencode_stats(days=days, cwd=cwd or self.cwd)
        raise NotImplementedError(f"stats not supported for {self.provider}")

    async def _claude_auth_status(self) -> AuthStatus:
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
        except (AgentProcessError, json.JSONDecodeError) as e:
            logger.warning("Claude auth status check failed: %s", e)
            return AuthStatus(authenticated=False, provider="claude")

    async def _gemini_auth_status(self) -> AuthStatus:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "--version"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=10.0,
        )
        try:
            await self.executor.run(spec)
            return AuthStatus(authenticated=True, provider="gemini")
        except AgentProcessError as e:
            logger.warning("Gemini auth status check failed: %s", e)
            return AuthStatus(authenticated=False, provider="gemini")

    async def _opencode_auth_status(self) -> AuthStatus:
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
        except AgentProcessError as e:
            logger.warning("OpenCode auth status check failed: %s", e)
            return AuthStatus(authenticated=False, provider="opencode")

    async def _antigravity_auth_status(self) -> AuthStatus:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "models"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=10.0,
        )
        try:
            await self.executor.run(spec)
            return AuthStatus(authenticated=True, provider=self.provider)
        except AgentProcessError as e:
            logger.warning("Antigravity auth status check failed: %s", e)
            return AuthStatus(authenticated=False, provider=self.provider)

    async def _antigravity_list_models(self) -> list[ModelInfo]:
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
                if line and "Fetching available models..." not in line:
                    models.append(ModelInfo(id=line, provider="antigravity"))
            return models
        except AgentProcessError as e:
            logger.warning("Antigravity list models failed: %s", e)
            return []

    async def _gemini_list_sessions(self, cwd: str) -> list[SessionEntry]:
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
        except AgentProcessError as e:
            logger.warning("Gemini list sessions failed: %s", e)
            return []

    async def _opencode_list_sessions(self, cwd: str) -> list[SessionEntry]:
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
        except AgentProcessError as e:
            logger.warning("OpenCode list sessions failed: %s", e)
            return []

    async def _opencode_list_models(self) -> list[ModelInfo]:
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
        except AgentProcessError as e:
            logger.warning("OpenCode list models failed: %s", e)
            return []

    async def _opencode_stats(self, *, days: int | None = None, cwd: str) -> dict:
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
        except AgentProcessError as e:
            logger.warning("OpenCode stats failed: %s", e)
            return {"raw": ""}

    async def _claude_auth_login(self, *, method: str | None = None) -> AuthStatus:
        cmd = [self._provider_instance.binary_name, "auth", "login"]
        if method:
            cmd.extend([f"--{method}"])
        spec = CommandSpec(argv=cmd, stdin="", env=self._provider_instance.build_env(), timeout=120.0)
        try:
            await self.executor.run(spec)
            return AuthStatus(authenticated=True, provider="claude", method=method)
        except AgentProcessError as e:
            logger.warning("Claude auth login failed: %s", e)
            return AuthStatus(authenticated=False, provider="claude")

    async def _claude_auth_logout(self) -> AuthStatus:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "auth", "logout"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            await self.executor.run(spec)
            return AuthStatus(authenticated=False, provider="claude")
        except AgentProcessError as e:
            logger.warning("Claude auth logout failed: %s", e)
            return AuthStatus(authenticated=False, provider="claude")

    async def _opencode_auth_login(self) -> AuthStatus:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "providers", "login"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=120.0,
        )
        try:
            await self.executor.run(spec)
            return AuthStatus(authenticated=True, provider="opencode")
        except AgentProcessError as e:
            logger.warning("OpenCode auth login failed: %s", e)
            return AuthStatus(authenticated=False, provider="opencode")

    async def _opencode_auth_logout(self) -> AuthStatus:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "providers", "logout"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            await self.executor.run(spec)
            return AuthStatus(authenticated=False, provider="opencode")
        except AgentProcessError as e:
            logger.warning("OpenCode auth logout failed: %s", e)
            return AuthStatus(authenticated=False, provider="opencode")

    async def _opencode_delete_session(self, session_id: str, cwd: str) -> bool:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "session", "delete", session_id],
            stdin="",
            cwd=cwd,
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            await self.executor.run(spec)
            return True
        except AgentProcessError as e:
            logger.warning("OpenCode delete session '%s' failed: %s", session_id, e)
            return False

    async def _opencode_export_session(self, session_id: str, cwd: str) -> SessionExport:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "export", session_id, "--format", "json"],
            stdin="",
            cwd=cwd,
            env=self._provider_instance.build_env(),
            timeout=30.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            return SessionExport(session_id=session_id, data=stdout, format="json")
        except AgentProcessError as e:
            logger.warning("OpenCode export session '%s' failed: %s", session_id, e)
            return SessionExport(session_id=session_id, data="", format="json")

    async def _opencode_import_session(self, data: str, cwd: str) -> str | None:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "import", "-"],
            stdin=data,
            cwd=cwd,
            env=self._provider_instance.build_env(),
            timeout=30.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            for line in stdout.strip().splitlines():
                line = line.strip()
                if line:
                    return line
            return None
        except AgentProcessError as e:
            logger.warning("OpenCode import session failed: %s", e)
            return None

    async def _claude_mcp_add(
        self,
        name: str,
        *,
        url: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        scope: str | None = None,
    ) -> bool:
        if url:
            cmd = [self._provider_instance.binary_name, "mcp", "add", name, "-t", "sse", "--url", url]
            if headers:
                for k, v in headers.items():
                    cmd.extend(["--header", f"{k}:{v}"])
        elif command:
            cmd = [self._provider_instance.binary_name, "mcp", "add", name, "-t", "stdio", command]
            if args:
                cmd.extend(args)
        else:
            return False
        if scope:
            cmd.extend(["--scope", scope])
        if env:
            cmd.extend(["-e", json.dumps(env)])
        spec = CommandSpec(argv=cmd, stdin="", env=self._provider_instance.build_env(), timeout=15.0)
        try:
            await self.executor.run(spec)
            return True
        except AgentProcessError as e:
            logger.warning("Claude MCP add '%s' failed: %s", name, e)
            return False

    async def _claude_mcp_remove(self, name: str, *, scope: str | None = None) -> bool:
        cmd = [self._provider_instance.binary_name, "mcp", "remove", name]
        if scope:
            cmd.extend(["--scope", scope])
        spec = CommandSpec(argv=cmd, stdin="", env=self._provider_instance.build_env(), timeout=15.0)
        try:
            await self.executor.run(spec)
            return True
        except AgentProcessError as e:
            logger.warning("Claude MCP remove '%s' failed: %s", name, e)
            return False

    async def _claude_mcp_list(self) -> list[McpServerInfo]:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "mcp", "list"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            servers: list[McpServerInfo] = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                if line and not line.startswith("No"):
                    servers.append(McpServerInfo(name=line))
            return servers
        except AgentProcessError as e:
            logger.warning("Claude MCP list failed: %s", e)
            return []

    async def _opencode_mcp_add(
        self,
        name: str,
        *,
        url: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> bool:
        if url:
            cmd = [self._provider_instance.binary_name, "mcp", "add", name, "-t", "sse", "--url", url]
        elif command:
            cmd = [self._provider_instance.binary_name, "mcp", "add", name, "-t", "stdio", command]
            if args:
                cmd.extend(args)
        else:
            return False
        if env:
            for k, v in env.items():
                cmd.extend(["-e", f"{k}={v}"])
        spec = CommandSpec(argv=cmd, stdin="", env=self._provider_instance.build_env(), timeout=15.0)
        try:
            await self.executor.run(spec)
            return True
        except AgentProcessError as e:
            logger.warning("OpenCode MCP add '%s' failed: %s", name, e)
            return False

    async def _opencode_mcp_remove(self, name: str) -> bool:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "mcp", "remove", name],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            await self.executor.run(spec)
            return True
        except AgentProcessError as e:
            logger.warning("OpenCode MCP remove '%s' failed: %s", name, e)
            return False

    async def _opencode_mcp_list(self) -> list[McpServerInfo]:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "mcp", "list"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            servers: list[McpServerInfo] = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                if line and not line.startswith("No"):
                    servers.append(McpServerInfo(name=line))
            return servers
        except AgentProcessError as e:
            logger.warning("OpenCode MCP list failed: %s", e)
            return []

    async def _gemini_list_extensions(self) -> list[ExtensionInfo]:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "extensions", "list"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            extensions: list[ExtensionInfo] = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                if line:
                    extensions.append(ExtensionInfo(name=line))
            return extensions
        except AgentProcessError as e:
            logger.warning("Gemini list extensions failed: %s", e)
            return []

    async def _claude_doctor(self) -> dict:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "doctor"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=30.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            return {"raw": stdout}
        except AgentProcessError as e:
            logger.warning("Claude doctor failed: %s", e)
            return {"raw": ""}

    async def _mimo_auth_status(self) -> AuthStatus:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "providers", "list"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            has_any = "0 credentials" not in stdout and len(stdout.strip()) > 0
            return AuthStatus(authenticated=has_any, provider="mimo")
        except AgentProcessError as e:
            logger.warning("MiMoCode auth status check failed: %s", e)
            return AuthStatus(authenticated=False, provider="mimo")

    async def _mimo_auth_login(self) -> AuthStatus:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "providers", "login"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=120.0,
        )
        try:
            await self.executor.run(spec)
            return AuthStatus(authenticated=True, provider="mimo")
        except AgentProcessError as e:
            logger.warning("MiMoCode auth login failed: %s", e)
            return AuthStatus(authenticated=False, provider="mimo")

    async def _mimo_auth_logout(self) -> AuthStatus:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "providers", "logout"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            await self.executor.run(spec)
            return AuthStatus(authenticated=False, provider="mimo")
        except AgentProcessError as e:
            logger.warning("MiMoCode auth logout failed: %s", e)
            return AuthStatus(authenticated=False, provider="mimo")

    async def _mimo_list_sessions(self, cwd: str) -> list[SessionEntry]:
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
                if line and not line.startswith("Session ID"):
                # Parse tabular output: first column is session ID
                    parts = line.split()
                    if parts and parts[0].startswith("ses_"):
                        title = " ".join(parts[1:]) if len(parts) > 1 else None
                        entries.append(SessionEntry(session_id=parts[0], title=title, provider="mimo"))
            return entries
        except AgentProcessError as e:
            logger.warning("MiMoCode list sessions failed: %s", e)
            return []

    async def _mimo_delete_session(self, session_id: str, cwd: str) -> bool:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "session", "delete", session_id],
            stdin="",
            cwd=cwd,
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            await self.executor.run(spec)
            return True
        except AgentProcessError as e:
            logger.warning("MiMoCode delete session '%s' failed: %s", session_id, e)
            return False

    async def _mimo_export_session(self, session_id: str, cwd: str) -> SessionExport:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "export", session_id],
            stdin="",
            cwd=cwd,
            env=self._provider_instance.build_env(),
            timeout=30.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            return SessionExport(session_id=session_id, data=stdout, format="json")
        except AgentProcessError as e:
            logger.warning("MiMoCode export session '%s' failed: %s", session_id, e)
            return SessionExport(session_id=session_id, data="", format="json")

    async def _mimo_list_models(self) -> list[ModelInfo]:
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
                    models.append(ModelInfo(id=line, provider="mimo"))
            return models
        except AgentProcessError as e:
            logger.warning("MiMoCode list models failed: %s", e)
            return []

    async def _mimo_mcp_add(
        self,
        name: str,
        *,
        url: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> bool:
        cmd = [self._provider_instance.binary_name, "mcp", "add", name]
        if command:
            cmd.extend([command])
            if args:
                cmd.extend(args)
        else:
            return False
        if env:
            for k, v in env.items():
                cmd.extend(["-e", f"{k}={v}"])
        spec = CommandSpec(argv=cmd, stdin="", env=self._provider_instance.build_env(), timeout=15.0)
        try:
            await self.executor.run(spec)
            return True
        except AgentProcessError as e:
            logger.warning("MiMoCode MCP add '%s' failed: %s", name, e)
            return False

    async def _mimo_mcp_remove(self, name: str) -> bool:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "mcp", "remove", name],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            await self.executor.run(spec)
            return True
        except AgentProcessError as e:
            logger.warning("MiMoCode MCP remove '%s' failed: %s", name, e)
            return False

    async def _mimo_mcp_list(self) -> list[McpServerInfo]:
        spec = CommandSpec(
            argv=[self._provider_instance.binary_name, "mcp", "list"],
            stdin="",
            env=self._provider_instance.build_env(),
            timeout=15.0,
        )
        try:
            stdout, _stderr = await self.executor.run(spec)
            servers: list[McpServerInfo] = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                _skip_prefixes = ("No", "┌", "└", "│")
                if line and not line.startswith(_skip_prefixes):
                    servers.append(McpServerInfo(name=line))
            return servers
        except AgentProcessError as e:
            logger.warning("MiMoCode MCP list failed: %s", e)
            return []
