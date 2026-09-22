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
| Node.js | `v22.23.2` through nvm `0.40.4` |
| npm | `10.9.8` |
| Provider | `deepseek` |
| Default model | `deepseek-flash` |
| API base URL | `https://api.deepseek.com/v1` |
| Default terminal directory | `/mnt/d/CodexApp/Project13/Git` |

The installation includes the Hermes CLI, ACP entry point, browser and
computer-use support, terminal and file tools, memory, skills, cron, and
Playwright Chromium. DeepSeek Flash inference and terminal-tool execution have
been verified with real calls, so the local agent workflow is operational.
Node.js, npm, npx, and corepack are available from `/usr/local/bin` in
non-login shells; `infra/wsl/configure-node.sh` maintains that integration.

## Install or refresh

From Windows PowerShell:

```powershell
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -u mars -- bash -lc `
  'cd /mnt/d/CodexApp/Project13/Git && bash infra/wsl/install-hermes.sh'
```

The script:

1. checks the reviewed installer SHA256;
2. installs the small set of Ubuntu build and media dependencies if missing;
3. configures the nvm-managed Node.js toolchain and stable `/usr/local/bin`
   links;
4. runs the official installer with `CI=1` and `--skip-setup`;
5. runs configuration repair and diagnostics without writing API keys; and
6. writes a timestamped log under `logs/`.

To update an existing installation, use:

```bash
cd /mnt/d/CodexApp/Project13/Git
bash infra/wsl/install-hermes.sh --update
```

## Current inference configuration

The active configuration is:

```bash
hermes config get model.provider
hermes config get model.default
hermes config get model.base_url
```

Expected values:

```text
deepseek
deepseek-flash
https://api.deepseek.com/v1
```

The API credential is stored only in `~/.hermes/.env`. Verify inference without
reading or printing that file:

```bash
hermes -z "Reply with exactly HERMES_OK and nothing else."
```

To replace the provider or model later, use `hermes model` or
`hermes setup --reconfigure`. The machine has no NVIDIA GPU, so a local large
model is not the default path.

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

`hermes doctor` reports DeepSeek connectivity as healthy. Its remaining
actionable message concerns optional full-tool credentials such as messaging,
X Search, image generation, or vision; these tools remain disabled until their
own credentials or dependencies are configured. The bundled Python also
reports a non-blocking SQLite `3.45.1` WAL-reset advisory; Hermes currently
uses rollback journal mode for `state.db`, which the installation workflow
treats as an accepted local warning.

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
