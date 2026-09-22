# New Conversation Context

Last updated: 2026-09-22

This is the canonical handoff file for a new Codex or Hermes conversation. It
records the verified local infrastructure and the exact commands needed to
resume work without rebuilding the environment. Secrets are never recorded
here.

## Read these first

1. `README.md`
2. `docs/SYSTEM_ARCHITECTURE.md`
3. `docs/DEPLOYMENT_STATUS.md`
4. `docs/INFRASTRUCTURE.md`
5. `docs/LOGGING_AND_ROLLBACK.md`
6. `docs/NETWORK_AND_PROXY.md`
7. `docs/HERMES_WSL.md`
8. `docs/CONDITION_MAPPING.md`
9. `docs/SYNTHETIC_CONDITIONS.md`

## Fast start

Open Ubuntu and start Hermes from the project repository:

```powershell
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -u mars
```

```bash
cd /mnt/d/CodexApp/Project13/Git
hermes --tui
```

Non-interactive smoke test:

```bash
cd /mnt/d/CodexApp/Project13/Git
hermes -z "Reply with exactly HERMES_OK and nothing else."
```

Expected output:

```text
HERMES_OK
```

## Current machine layout

| Item | Path |
|---|---|
| Repository | `D:\CodexApp\Project13\Git` |
| Existing data tree | `D:\CodexApp\Project13\EcoliOmics` |
| WSL distro | `Ubuntu-24.04` |
| WSL VHDX root | `D:\WSL\Ubuntu-24.04` |
| Ubuntu rootfs archive | `D:\WSL\Downloads\ubuntu-base-24.04.5-base-amd64.tar.gz` |
| Modern WSL MSI | `D:\WSL\Downloads\wsl.2.7.14.0.x64.msi` |
| Docker Desktop | `D:\DockerDesktop` |
| Docker WSL data | `D:\DockerDesktopData` |
| Hermes home | `/home/mars/.hermes` in `Ubuntu-24.04` |
| Hermes code | `/home/mars/.hermes/hermes-agent` in `Ubuntu-24.04` |
| Hermes default terminal directory | `/mnt/d/CodexApp/Project13/Git` |
| Logs | `D:\CodexApp\Project13\Git\logs` |
| Local Git backup | `D:\CodexApp\Project13\GitBackup.git` |

## Verified runtime

- Windows remains Windows 10 Home 22H2 build 19045; no Windows upgrade was
  performed.
- Microsoft WSL runtime `2.7.14` is installed and uses Linux kernel
  `6.18.33.2-microsoft-standard-WSL2`.
- Ubuntu `24.04` is installed as `Ubuntu-24.04`, running as WSL2.
- The Linux user is `mars`; its password has been set and is intentionally not
  stored in this repository.
- Git, Python, build tools, `uv 0.12.17`, and the base developer packages are
  installed in Ubuntu.
- Node.js `v22.23.2` and npm `10.9.8` are installed through nvm.
- Docker Desktop `4.91.0` and Engine `29.8.0` are installed and working.
- Docker WSL integration is enabled for `Ubuntu-24.04`.
- Docker Desktop is configured to use the Clash Verge proxy
  `http://127.0.0.1:7897`.
- Ubuntu has an idempotent shell proxy block installed by
  `infra/wsl/configure-proxy.sh`; its template is
  `infra/wsl/project13-proxy.bashrc`.
- Clash LAN access is enabled, system proxy and TUN mode are disabled, and the
  Windows Firewall rule `Project13 Clash Verge WSL 7897` is restricted to
  `172.16.0.0/12`.
- The `hello-world` image was pulled and executed successfully from Ubuntu.

## Hermes Agent

- Version: `v0.21.4 (2026.9.21)`, upstream `836b5f82`.
- Command: `/home/mars/.local/bin/hermes`.
- Configuration version: `v45`.
- Provider: `deepseek`.
- Default model: `deepseek-flash`.
- API base URL: `https://api.deepseek.com/v1`.
- Credential location: `/home/mars/.hermes/.env` on this machine only.
- Terminal backend: local.
- Default terminal directory: `/mnt/d/CodexApp/Project13/Git`.
- Verified capabilities include CLI and ACP, terminal, file, browser,
  browser-use, computer_use, web search/extract, memory, skills, cron,
  project, todo, session search, TTS, and code execution.
- DeepSeek connectivity is reported healthy by `hermes doctor`.
- A real inference smoke test returned `HERMES_OK`.
- A real terminal-tool test returned the repository worktree and
  `## main...origin/main`.
- Optional integrations requiring separate credentials or systems remain
  disabled when their dependency is absent. The current actionable doctor item
  is only for optional full-tool credentials, not core agent inference.

Do not print, copy, commit, or include the API key in a conversation. A new
conversation should verify behavior through commands, not by reading `.env`.

## Git and network

- The repository is connected to
  `https://github.com/PrzmArk77469/E.coli-Multi-Omics-World-Model-Test-Demo.git`
  as `origin`.
- A local rollback remote named `backup` points to
  `D:\CodexApp\Project13\GitBackup.git`.
- Current branch: `main`.
- Use `git log -1 --oneline` as the authoritative current revision.
- The infrastructure snapshot was fully reverified at
  `2026-09-22 17:33:04 +08:00`.
- `origin/main` and `backup/main` are synchronized after each verified
  documentation or code change.
- Docker and GitHub traffic use the verified Clash Verge proxy path.
- The latest complete infrastructure verification is
  `logs/last-verification.json`.

## Project data and Demo

- An observed-only sample-condition registry is generated at
  `D:\CodexApp\Project13\EcoliOmics\integrated\condition_completion`. It keeps
  source evidence separate from any future synthetic sidecar.
- A condition-aware seed-42 Demo is generated under
  `D:\CodexApp\Project13\EcoliOmics\integrated\condition_completion\demo_full`.
  Its synthetic sidecar is explicitly separated from observed metadata.
- The same Demo exports an offline interactive 3D replay viewer at
  `demo_full\visualization\demo_visualization.html`. It shows all 2,000
  agents, event outcomes, complexes, timeline controls, and condition
  provenance. Serve that directory over local HTTP; the generated data file is
  intentionally not committed.

## Verification commands

Project tests:

```bash
cd /mnt/d/CodexApp/Project13/Git
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Expected result: `16` tests pass.

Hermes inference:

```bash
hermes config get model.provider
hermes config get model.default
hermes doctor
hermes -z "Reply with exactly HERMES_OK and nothing else."
```

Expected model settings:

```text
deepseek
deepseek-flash
```

## Resume the infrastructure

Start Clash Verge so port `7897` is listening, then run:

```powershell
& D:\CodexApp\Project13\Git\Run-Infrastructure.cmd
```

The launcher self-elevates and bypasses the execution-policy restriction. If
the infrastructure is already running, use:

```powershell
& 'C:\Program Files\WSL\wsl.exe' -l -v
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -- git --version
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -- uv --version
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -- docker version
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -u mars -- bash -lc 'hermes --version'
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -u mars -- bash -lc 'hermes doctor'
& 'C:\Users\Mars\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe' -NoProfile -ExecutionPolicy Bypass -File D:\CodexApp\Project13\Git\infra\windows\04-Verify-Infrastructure.ps1
```

## New conversation protocol

1. Read this file, `docs/SYSTEM_ARCHITECTURE.md`, and
   `docs/DEPLOYMENT_STATUS.md`.
2. Run `git status --short --branch` before edits.
3. Use Hermes from `/mnt/d/CodexApp/Project13/Git`; its terminal commands
   already default to that directory.
4. Run the inference smoke test before relying on Hermes for a long workflow.
5. Keep observed data, synthetic data, generated artifacts, credentials, and
   logs in their documented local locations.
6. Commit and push verified repository changes to both `origin` and `backup`.

## Do not do

- Do not commit `D:\CodexApp\Project13\EcoliOmics\raw`.
- Do not store SSH keys, cloud credentials, or API tokens in the repository.
- Do not unregister `Ubuntu-24.04` before exporting a backup.
- Do not upgrade Windows merely to make Docker work; the current stack is
  already operational on Windows 10 build 19045.
- Do not run `wsl --shutdown` or an automated `wsl --terminate` during setup.
  The legacy Windows 10 service can enter `STOP_PENDING`; see the rollback
  document for the controlled recovery procedure.
- Do not use a third-party Docker registry mirror when the verified Clash
  proxy path is available.
- Do not place Hermes API keys, OAuth tokens, or provider credentials in the
  repository or infrastructure logs.
