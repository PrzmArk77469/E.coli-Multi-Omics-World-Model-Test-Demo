# Nous Research Hermes Agent in WSL

Last updated: 2026-09-22

## Scope

The local agent layer is the official Nous Research Hermes Agent. It runs as
the Ubuntu user `mars` and uses the existing WSL, Docker, Git, and proxy
foundation. The installer and runtime come only from the official
`hermes-agent.nousresearch.com` and `NousResearch/hermes-agent` sources.

## Verified local state

| Item | Value |
|---|---|
| Version | Hermes Agent `v0.21.4` (2026.9.21) |
| Upstream commit | `836b5f82` |
| Install method | Git |
| Command | `/home/mars/.local/bin/hermes` |
| Code | `/home/mars/.hermes/hermes-agent` |
| Configuration | `/home/mars/.hermes/config.yaml` |
| Credentials | `/home/mars/.hermes/.env` (local only) |
| Persona | `/home/mars/.hermes/SOUL.md` |
| Runtime state | `/home/mars/.hermes/` |
| Browser cache | `/home/mars/.cache/ms-playwright` |

The installation includes the Hermes CLI, ACP entry point, browser and
computer-use support, terminal and file tools, memory, skills, cron, and
Playwright Chromium. Model inference is not authenticated yet, so chat is the
only major workflow that remains disabled.

## Install or refresh

From Windows PowerShell:

```powershell
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -u mars -- bash -lc `
  'cd /mnt/d/CodexApp/Project13/Git && bash infra/wsl/install-hermes.sh'
```

The script:

1. checks the reviewed installer SHA256;
2. installs the small set of Ubuntu build and media dependencies if missing;
3. runs the official installer with `CI=1` and `--skip-setup`;
4. runs configuration repair and diagnostics without writing API keys; and
5. writes a timestamped log under `logs/`.

To update an existing installation, use:

```bash
cd /mnt/d/CodexApp/Project13/Git
bash infra/wsl/install-hermes.sh --update
```

## Configure inference

The recommended first setup is the Nous Portal OAuth path:

```bash
hermes setup --portal
```

Alternatively, run the interactive model picker:

```bash
hermes model
```

The machine has no NVIDIA GPU, so a local large model is not the default path.
Use Nous Portal or another hosted provider. Credentials stay in
`~/.hermes/.env` or the provider's OAuth store and must never be committed.

## Start and inspect

```bash
cd /mnt/d/CodexApp/Project13/Git
hermes --tui
hermes doctor
hermes status
hermes sessions list
```

Useful non-interactive checks:

```bash
hermes --version
hermes doctor --fix
hermes security
```

`hermes doctor` reports one expected remaining issue until a model provider is
authenticated. Optional messaging, X Search, image generation, and vision
tools remain disabled until their credentials or dependencies are configured.
The bundled Python also reports a non-blocking SQLite `3.45.1` WAL-reset
advisory; Hermes currently uses rollback journal mode for `state.db`, which the
installation workflow treats as an accepted local warning.

## Logs and rollback

Installation logs are stored under:

```text
D:\CodexApp\Project13\Git\logs\hermes-install-*.log
```

Hermes runtime logs and session state are stored under `~/.hermes/`.

Before a major update:

```bash
hermes backup
hermes update --plan
```

To roll back code and dependencies, use the normal Git history of
`~/.hermes/hermes-agent`, or restore a `hermes backup` archive with:

```bash
hermes import <backup.zip>
```

Do not delete the repository, the Ubuntu distribution, or the project data
tree while recovering Hermes. Re-run the reviewed install script after the
Hermes home directory has been restored.
