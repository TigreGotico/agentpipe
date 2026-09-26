"""First-run provisioning and credential report for the provider CLIs.

The Docker image bundles a handful of coding-agent CLIs. Each one keeps its
credentials somewhere different, and some of them refuse to start until their
config directory exists. This module reports what is installed, what has usable
credentials, and what is missing, then creates the directories a CLI needs to
start cleanly.

It is deliberately boring: standard library only, no network, no interaction.
It never writes a credential, never overwrites a file that already exists, and
never prints a secret — only the name of the variable or the path of the file
that holds it.

Run it standalone to diagnose a container::

    docker compose run --rm agentpipe python -m agentpipe.provision

``docker-entrypoint.sh`` runs it on startup, before the server binds a port.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── what "provisioned" means, per CLI ─────────────────────────────────
#
# ``env_keys``  — environment variables the CLI accepts as a credential.
# ``cred_globs``— home-relative globs whose presence means a stored login.
# ``dirs``      — home-relative directories the CLI needs to exist to start.
# ``free_tier`` — the CLI answers prompts with no credentials at all.


@dataclass(frozen=True)
class CliSpec:
    binary: str
    bundled: bool
    env_keys: tuple[str, ...] = ()
    cred_globs: tuple[str, ...] = ()
    dirs: tuple[str, ...] = ()
    free_tier: bool = False
    note: str = ""
    install: str = ""


CLI_SPECS: tuple[CliSpec, ...] = (
    CliSpec(
        binary="kilo",
        bundled=True,
        env_keys=("KILO_API_KEY", "KILO_AUTH_CONTENT", "OPENROUTER_API_KEY"),
        cred_globs=(".local/share/kilo/auth.json",),
        dirs=(".config/kilo", ".local/share/kilo", ".local/state/kilo", ".cache/kilo"),
        free_tier=True,
        note="free-tier models work with no credentials",
    ),
    CliSpec(
        binary="opencode",
        bundled=True,
        env_keys=("OPENCODE_API_KEY", "OPENCODE_AUTH_CONTENT", "OPENROUTER_API_KEY"),
        cred_globs=(".local/share/opencode/auth.json",),
        dirs=(".config/opencode", ".local/share/opencode", ".local/state/opencode", ".cache/opencode"),
        free_tier=True,
        note="free-tier models work with no credentials",
    ),
    CliSpec(
        binary="gemini",
        bundled=True,
        env_keys=("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"),
        cred_globs=(".gemini/oauth_creds.json", ".gemini/google_accounts.json"),
        dirs=(".gemini",),
        note="Google dropped unpaid tiers on 2026-06-18; needs a paid account",
    ),
    CliSpec(
        binary="aider",
        bundled=True,
        env_keys=(
            "OPENROUTER_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "DEEPSEEK_API_KEY",
            "AIDER_OPENAI_API_KEY",
            "AIDER_ANTHROPIC_API_KEY",
        ),
        cred_globs=(".aider.conf.yml", ".env"),
        note="reads keys from the environment or ~/.aider.conf.yml",
    ),
    CliSpec(
        binary="vibe",
        bundled=True,
        env_keys=("MISTRAL_API_KEY",),
        cred_globs=(".vibe/.env",),
        dirs=(".vibe",),
        note="VIBE_HOME defaults to ~/.vibe; keys live in ~/.vibe/.env",
    ),
    CliSpec(
        binary="qodercli",
        bundled=True,
        env_keys=("QODER_AUTH_MANAGED_TOKEN",),
        cred_globs=(".qoder/auth.json", ".qoder/credentials.json", ".qoder/*token*.json"),
        dirs=(".qoder",),
        note="log in once inside the container and keep ~/.qoder on a volume",
    ),
    CliSpec(
        binary="claude",
        bundled=False,
        env_keys=("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"),
        cred_globs=(".claude/.credentials.json", ".claude.json"),
        dirs=(".claude",),
        install="curl -fsSL https://claude.ai/install.sh | bash",
    ),
    CliSpec(
        binary="agy",
        bundled=False,
        note="Antigravity CLI; not bundled and has no unattended install",
    ),
    CliSpec(
        binary="mimo",
        bundled=False,
        note="MiMo Code CLI; not bundled and has no unattended install",
    ),
)


@dataclass
class CliStatus:
    spec: CliSpec
    installed: bool
    path: str | None = None
    env_found: list[str] = field(default_factory=list)
    creds_found: list[str] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    unwritable: list[str] = field(default_factory=list)

    @property
    def has_credentials(self) -> bool:
        return bool(self.env_found or self.creds_found)

    @property
    def usable(self) -> bool:
        """Can this CLI answer a prompt right now?"""
        return self.installed and (self.has_credentials or self.spec.free_tier)

    @property
    def missing(self) -> str:
        if not self.installed:
            if self.spec.install:
                return f"not installed — {self.spec.install}"
            return "not installed — not bundled in this image"
        if self.has_credentials:
            return ""
        if self.spec.free_tier:
            return ""
        if not self.spec.env_keys:
            return "no credentials"
        keys = list(self.spec.env_keys[:3])
        if len(self.spec.env_keys) > 3:
            keys.append("...")
        return "no credentials — set " + " or ".join(keys)


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def _find_creds(spec: CliSpec, home: Path) -> list[str]:
    """Home-relative paths of non-empty credential files that already exist."""
    found: list[str] = []
    for pattern in spec.cred_globs:
        for match in sorted(home.glob(pattern)):
            try:
                if match.is_file() and match.stat().st_size > 0:
                    found.append(str(match))
            except OSError:
                continue
    return found


def _ensure_dirs(spec: CliSpec, home: Path, *, dry_run: bool) -> tuple[list[str], list[str]]:
    """Create the directories a CLI needs. Returns (created, unwritable).

    Existing directories are left exactly as they are. A read-only root is not
    an error: the path is reported and the caller carries on.
    """
    created: list[str] = []
    unwritable: list[str] = []
    for rel in spec.dirs:
        target = home / rel
        if target.is_dir():
            if not os.access(target, os.W_OK):
                unwritable.append(str(target))
            continue
        if dry_run:
            created.append(str(target))
            continue
        try:
            target.mkdir(parents=True, exist_ok=True)
            created.append(str(target))
        except OSError:
            unwritable.append(str(target))
    return created, unwritable


def inspect(spec: CliSpec, *, home: Path | None = None, environ: dict[str, str] | None = None,
            create: bool = True, dry_run: bool = False) -> CliStatus:
    """Report on one CLI, optionally creating the directories it needs."""
    home = home or _home()
    environ = os.environ if environ is None else environ
    path = shutil.which(spec.binary)
    status = CliStatus(spec=spec, installed=path is not None, path=path)
    status.env_found = [k for k in spec.env_keys if (environ.get(k) or "").strip()]
    status.creds_found = _find_creds(spec, home)
    if create and status.installed:
        status.created, status.unwritable = _ensure_dirs(spec, home, dry_run=dry_run)
    return status


def inspect_all(*, home: Path | None = None, environ: dict[str, str] | None = None,
                create: bool = True, dry_run: bool = False) -> list[CliStatus]:
    return [
        inspect(spec, home=home, environ=environ, create=create, dry_run=dry_run)
        for spec in CLI_SPECS
    ]


def format_report(statuses: list[CliStatus]) -> str:
    """Render the startup banner. Prints names of secrets, never values."""
    lines: list[str] = ["Provider CLIs:"]
    for st in statuses:
        if not st.installed:
            lines.append(f"  [MISS] {st.spec.binary:<9} {st.missing}")
            continue
        detail: list[str] = []
        if st.env_found:
            detail.append("env: " + ", ".join(st.env_found))
        if st.creds_found:
            detail.append("login: " + ", ".join(st.creds_found))
        if not detail and st.spec.free_tier:
            detail.append("free tier, no credentials needed")
        tag = "OK  " if st.usable else "AUTH"
        lines.append(f"  [{tag}] {st.spec.binary:<9} {'; '.join(detail)}".rstrip())
        if not st.usable and st.missing:
            lines.append(f"         {st.missing}")
        if st.spec.note and not st.usable:
            lines.append(f"         {st.spec.note}")

    created = [p for st in statuses for p in st.created]
    unwritable = [p for st in statuses for p in st.unwritable]
    lines.append("")
    if created:
        lines.append("Created config directories:")
        lines.extend(f"  {p}" for p in created)
    if unwritable:
        lines.append("Read-only, could not create (mount a volume or tmpfs here):")
        lines.extend(f"  {p}" for p in unwritable)
    if not created and not unwritable:
        lines.append("Config directories: nothing to create.")

    usable = [st.spec.binary for st in statuses if st.usable]
    lines.append("")
    lines.append("Usable now: " + (", ".join(usable) if usable else "none"))
    if not usable:
        lines.append("  kilo and opencode need no credentials — check they are installed.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dry_run = "--dry-run" in argv
    strict = "--strict" in argv
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    statuses = inspect_all(create=True, dry_run=dry_run)
    print(format_report(statuses))
    if strict and not any(st.usable for st in statuses):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
