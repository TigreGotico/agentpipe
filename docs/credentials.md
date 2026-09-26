# Sharing Credentials with the Container

You do not need any of this to get started. `kilo` and `opencode` answer prompts
on their free-tier models with no account and no API key, and that is what the
container does out of the box:

```bash
docker compose up -d
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "opencode/deepseek-v4-flash-free", "messages": [{"role": "user", "content": "say hi"}]}'
```

Read on only if you want a paid model, or a CLI that needs a login.

## Find out what the container already has

Ask it. The same report runs at startup and can be run on its own:

```bash
docker compose run --rm agentpipe python -m agentpipe.provision
```

```
Provider CLIs:
  [OK  ] kilo      free tier, no credentials needed
  [OK  ] opencode  free tier, no credentials needed
  [AUTH] gemini
         no credentials — set GEMINI_API_KEY or GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS
  [AUTH] vibe
         no credentials — set MISTRAL_API_KEY
         VIBE_HOME defaults to ~/.vibe; keys live in ~/.vibe/.env
  [MISS] claude    not installed — curl -fsSL https://claude.ai/install.sh | bash
  [MISS] agy       not installed — not bundled in this image
  [MISS] mimo      not installed — not bundled in this image

Usable now: kilo, opencode
```

`OK` means the CLI can answer a prompt right now. `AUTH` means the binary is
there but has nothing to authenticate with. `MISS` means the binary is not in
the image. The report prints the *name* of an environment variable and the
*path* of a credential file, never their contents.

## Read this before you mount anything

A credential mounted into a container is a credential given to everything
inside it. The programs inside this container are coding agents that run
whatever a prompt tells them to run, and if you have exposed the HTTP server,
the prompts come from outside. Mounting `~/.claude` gives a stranger's prompt
your Claude subscription; mounting `~/.gemini` gives it your Google account.

Two rules make this survivable. Mount read-only unless you need the CLI to
refresh its own token. And do not mount host credentials at all on a server
that answers requests you did not send — use
[`docker-compose.stateless.yml`](../docker-compose.stateless.yml), which mounts
nothing from the host and serves only the free models.

## What to mount, per CLI

The container runs as root, so the container-side home is `/root`.

| CLI | Host path | Container path | Read-only? |
|-----|-----------|----------------|------------|
| `kilo` | `~/.local/share/kilo/auth.json` | `/root/.local/share/kilo/auth.json` | yes |
| `opencode` | `~/.local/share/opencode/auth.json` | `/root/.local/share/opencode/auth.json` | yes |
| `gemini` | `~/.gemini` | `/root/.gemini` | no |
| `vibe` | `~/.vibe/.env` | `/root/.vibe/.env` | yes |
| `qodercli` | `~/.qoder` | `/root/.qoder` | no |
| `aider` | `~/.aider.conf.yml` | `/root/.aider.conf.yml` | yes |
| `claude` | `~/.claude` and `~/.claude.json` | `/root/.claude`, `/root/.claude.json` | no |

Notes on the two that cannot be read-only. Gemini's OAuth credentials expire
and the CLI rewrites `~/.gemini/oauth_creds.json` when it refreshes them, so a
read-only mount works until the token ages out and then stops working. Qoder
keeps logs and run state in the same directory as its login, so it needs to
write there. Claude Code keeps mutable state in `~/.claude.json` as well as in
`~/.claude`.

Kilo and opencode are the good case: their whole login is one JSON file, so you
can mount the single file read-only and leave the rest of their state inside
the container.

Mount the file, not the directory, wherever the table names a file. Mounting
`~/.local/share/kilo` wholesale also hands over the session database, which
holds the text of every conversation you have had with that CLI on the host.

## Compose snippet

Copy this into your own `docker-compose.override.yml` and delete the lines for
the CLIs you do not use:

```yaml
services:
  agentpipe:
    volumes:
      - .:/workspace
      # One JSON file each. Read-only is enough.
      - ~/.local/share/kilo/auth.json:/root/.local/share/kilo/auth.json:ro
      - ~/.local/share/opencode/auth.json:/root/.local/share/opencode/auth.json:ro
      - ~/.vibe/.env:/root/.vibe/.env:ro
      - ~/.aider.conf.yml:/root/.aider.conf.yml:ro
      # These refresh their own tokens, so they need to write.
      - ~/.gemini:/root/.gemini
      - ~/.qoder:/root/.qoder
      - ~/.claude:/root/.claude
      - ~/.claude.json:/root/.claude.json
    environment:
      - AGENTPIPE_CWD=/workspace
```

Docker creates a *directory* when a bind source does not exist, so make sure
the host file is really there before you start. `docker compose config` will
show you the resolved paths.

## Keys instead of logins

Most of these CLIs take an API key from the environment, which is simpler than
mounting anything:

| Variable | Used by |
|----------|---------|
| `OPENROUTER_API_KEY` | aider, kilo, opencode |
| `MISTRAL_API_KEY` | vibe |
| `GEMINI_API_KEY`, `GOOGLE_API_KEY` | gemini |
| `ANTHROPIC_API_KEY` | aider, claude |
| `OPENAI_API_KEY` | aider, qodercli |

Put them in a `.env` file next to `docker-compose.yml`. The compose file already
passes the common ones through. A key in the environment is visible to anything
that can read `/proc` inside the container, which is the same trade-off as a
mounted credential file, but it is at least scoped to one key rather than a
whole account session.

## Authenticating inside the container instead

The other direction: log in once inside the container and keep the result in a
named volume, so it survives `docker compose down` without ever touching your
host credentials.

```yaml
services:
  agentpipe:
    volumes:
      - agentpipe-auth-kilo:/root/.local/share/kilo
      - agentpipe-auth-opencode:/root/.local/share/opencode
      - agentpipe-auth-gemini:/root/.gemini
      - agentpipe-auth-qoder:/root/.qoder
      - agentpipe-auth-vibe:/root/.vibe

volumes:
  agentpipe-auth-kilo:
  agentpipe-auth-opencode:
  agentpipe-auth-gemini:
  agentpipe-auth-qoder:
  agentpipe-auth-vibe:
```

Then log in once, interactively:

```bash
docker compose run --rm agentpipe kilo auth login
docker compose run --rm agentpipe opencode providers login
docker compose run --rm agentpipe vibe --setup
```

Check it took:

```bash
docker compose run --rm agentpipe python -m agentpipe.provision
```

These logins are interactive on purpose and cannot be automated. `kilo auth
login` and `opencode providers login` ask you to pick a provider and paste a
key. `gemini` and `claude` use a browser OAuth flow: they print a URL, you open
it on your own machine, and you paste the code back. There is no unattended
equivalent — if you need an unattended container, use an API key from the
environment, or copy a credential file that you obtained interactively
somewhere else.

## Read-only root filesystems

`docker-compose.stateless.yml` runs with `read_only: true`, so every directory
a CLI writes to has to be a tmpfs mount. The file already lists them. If you
build your own hardened deployment and forget one, the CLI usually dies without
a useful message — kilo prints a bare `Bun v1.3.14` line and nothing else. Run
the provisioning report to find out which path it wanted:

```
Read-only, could not create (mount a volume or tmpfs here):
  /root/.local/share/kilo
  /root/.config/kilo
```

## CLIs that are not in the image

`claude`, `agy` (Antigravity) and `mimo` (MiMo Code) are supported by the
Python library but are not bundled in `ghcr.io/tigregotico/agentpipe`. Running
the provisioning report in the stock image shows all three as `MISS`.

Claude Code has an installer you can run in the container, but it does not
survive a restart unless you bake it into your own image:

```bash
docker compose run --rm agentpipe bash -c "curl -fsSL https://claude.ai/install.sh | bash"
docker compose run --rm agentpipe claude auth login
```

The reliable way is a two-line Dockerfile of your own:

```dockerfile
FROM ghcr.io/tigregotico/agentpipe:latest
RUN curl -fsSL https://claude.ai/install.sh | bash
```

`agy` and `mimo` are distributed by their vendors and we do not ship an install
command for either, because we have not verified one that works unattended in a
plain Debian container. If you need them, install them in your own image from
the vendor's instructions and mount their credential directories the same way.
Once the binary is on `PATH`, agentpipe and the provisioning report pick it up
with no further configuration.

## Gemini's free tier is gone

The docs used to call Gemini free. It is not, any more. Google stopped serving
Google One and unpaid tiers on 18 June 2026, and agentpipe now raises
`RuntimeError` when you construct a Gemini provider rather than letting you
find out from a failed request. Use a paid Google account, or use `kilo` and
`opencode`, whose free tiers still work.

---
[← HTTP Server](server.md) · [Home](index.md) · [Auth and Quota →](auth-quota.md)
