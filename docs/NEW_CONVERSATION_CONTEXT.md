# New Conversation Context

Last updated: 2026-10-30

This is the authoritative handoff for a new Codex or Hermes conversation. It
records the current local infrastructure, completed environment work, unresolved
issues, and exact commands for resuming safely. Never record credentials here.

## Read these first

1. `README.md`
2. `docs/SYSTEM_ARCHITECTURE.md`
3. `docs/DEPLOYMENT_STATUS.md`
4. `docs/INFRASTRUCTURE.md`
5. `docs/PORTABLE_INFRASTRUCTURE.md`
6. `docs/INFRASTRUCTURE_READINESS.md`
7. `docs/NETWORK_AND_PROXY.md`
8. `docs/HERMES_WSL.md`
9. `docs/LOGGING_AND_ROLLBACK.md`
10. `docs/CONDITION_MAPPING.md`
11. `docs/SYNTHETIC_CONDITIONS.md`

`docs/INFRASTRUCTURE_READINESS.md` contains the 2026-10-29 assessment. Its top
section contains the 2026-10-30 status delta; use this handoff as the current
source of truth where the documents differ.

## Current objective

The local infrastructure is operational. The remaining work is environment
hardening and cross-surface integration:

- restore reliable WSL access to GitHub through Clash;
- finish the Linux-native Codex sandbox prerequisites;
- decide whether to repair `py` and `python3` aliases;
- refresh Hermes and address its dependency advisories;
- preserve the clean Windows PATH and isolated tool caches;
- keep the repository portable for a future project and new Git repository.

## Session summary

Completed in this working session:

- Added complete Node.js/nvm support to Ubuntu.
- Created `docs/PORTABLE_INFRASTRUCTURE.md` for a detached new-project setup.
- Created the infrastructure readiness assessment.
- Removed the global ChemDraw `PYTHONPATH` from the real `Mars` environment.
- Confirmed PowerShell 7.6.9 is installed system-wide.
- Confirmed uv 0.13.6 and Python 3.14.5 work.
- Copied real `uv.exe`, `uvx.exe`, and `uvw.exe` binaries into
  `C:\Users\Mars\.local\bin`.
- Added writable, isolated uv/pip/npm caches under the user TEMP directory.
- Persisted the Windows user PATH for Python, uv, npm, Docker, and WindowsApps.
- Removed PATH duplicates, missing entries, and trailing empty entries.
- Restored the valid `C:\Program Files\dotnet` system PATH entry after cleanup.
- Started Docker Desktop and verified Windows and Ubuntu access to the same
  Linux Engine.
- Ran `hello-world` from Ubuntu successfully.

Still open:

- WSL cannot currently reach `https://github.com` through Clash
  (`SSL_ERROR_SYSCALL`, HTTP `000`).
- WSL lacks `bubblewrap` and the Codex CLI, so Codex is not ready to run as a
  Linux-native agent inside WSL.
- `py` is missing and `python3` resolves to an unusable WindowsApps alias.
- Hermes is behind upstream and reports dependency advisories.
- CMake, Ninja, and MSVC are not globally on PATH; use the Visual Studio
  developer shell.
- No CUDA-capable GPU is available.

## Machine layout

| Item | Path |
|---|---|
| Repository | `D:\CodexApp\Project13\Git` |
| Existing data tree | `D:\CodexApp\Project13\EcoliOmics` |
| WSL distro | `Ubuntu-24.04` |
| WSL VHDX root | `D:\WSL\Ubuntu-24.04` |
| Docker Desktop | `D:\DockerDesktop` |
| Docker data | `D:\DockerDesktopData` |
| Windows user tools | `C:\Users\Mars\.local\bin` |
| uv-managed Python | `C:\Users\Mars\AppData\Roaming\uv\python` |
| uv cache | `C:\Users\Mars\AppData\Local\Temp\codex-cache\uv` |
| pip cache | `C:\Users\Mars\AppData\Local\Temp\codex-cache\pip` |
| npm cache | `C:\Users\Mars\AppData\Local\Temp\codex-cache\npm` |
| Hermes home | `/home/mars/.hermes` |
| Logs | `D:\CodexApp\Project13\Git\logs` |

## Windows state

- OS: Windows 10 Home China 22H2, build 19045.
- CPU: AMD Ryzen 7 4800U, 8 cores / 16 logical processors.
- RAM: 16 GB.
- GPU: AMD Radeon integrated graphics; no NVIDIA/CUDA device.
- PowerShell: system `7.6.9`; Codex's sandboxed shell currently uses its bundled
  `7.6.5`.
- Codex: `0.166.0-alpha.5.1`.
- Python: `D:\Python314\python.exe`, Python `3.14.5`.
- pip: `D:\Python314\Scripts\pip.exe`, pip `26.1.1`.
- uv: `0.13.6`; uv-managed Python `3.12.16` is also available.
- Node.js: `24.19.0`; npm `12.2.0`.
- Java: OpenJDK `21.0.6`; Java 8 still appears later in the system PATH.
- .NET SDK: `5.0.416`.
- Git: installed at `D:\Program Files\Git\cmd`.
- Docker CLI: `D:\DockerDesktop\resources\bin`.

### Current user PATH

```text
C:\Users\Mars\.local\bin
C:\Users\Mars\AppData\Local\Microsoft\WinGet\Links
D:\Python314
D:\Python314\Scripts
C:\Users\Mars\AppData\Roaming\npm
D:\DockerDesktop\resources\bin
C:\Users\Mars\AppData\Local\Microsoft\WindowsApps
```

As of this handoff:

- system PATH has 17 entries;
- user PATH has 7 entries;
- there are no duplicate or missing entries;
- there are no trailing empty entries;
- `PYTHONPATH` is absent from both Machine and User scopes.

External installers have re-added trailing empty PATH entries before. Recheck
after Docker, SDK, or language-runtime updates.

### Isolated tool caches

Persisted as user environment variables:

```text
UV_CACHE_DIR=C:\Users\Mars\AppData\Local\Temp\codex-cache\uv
PIP_CACHE_DIR=C:\Users\Mars\AppData\Local\Temp\codex-cache\pip
NPM_CONFIG_CACHE=C:\Users\Mars\AppData\Local\Temp\codex-cache\npm
```

All three directories are writable by both `Mars` and
`CodexSandboxUsers`. These caches are disposable and may be removed by normal
TEMP cleanup.

### Python policy

- Use `python`, not the WindowsApps `python3` alias.
- Use project-local `.venv` or `uv run`.
- Do not restore MGLTools Python 2.7 or ChemDraw paths to the global PATH.
- Do not set a global `PYTHONPATH`.
- Python 3.14 is verified for this repository: 16 tests pass.
- Prefer uv-managed Python 3.12 for projects that need broader binary-wheel or
  scientific-package compatibility.

## WSL state

- WSL runtime: `2.7.14`.
- Kernel: `6.18.33.2-microsoft-standard-WSL2`.
- Ubuntu: `24.04`, WSL2, running as user `mars`.
- WSL allocation: 8 processors, 9 GB RAM, 12 GB swap.
- Python: `/usr/bin/python3`, `3.12.3`.
- uv: `/usr/local/bin/uv`, `0.12.17`.
- Git: `2.43.0`.
- GCC/G++: `13.3.0`.
- Make: `4.3`.
- ffmpeg: `6.1.1`.
- Node.js: `/usr/local/bin/node`, `v22.23.2`.
- npm: `10.9.8`.
- Hermes: `/home/mars/.local/bin/hermes`.
- Docker client and server: connected through Docker Desktop.

Not installed in WSL:

- `bubblewrap`;
- Codex CLI;
- CMake and Ninja;
- R;
- Linux PowerShell.

Windows executables are reachable through WSL interop, including
`cmd.exe` and `pwsh.exe`.

## Docker state

- Docker Desktop: `4.91.0`.
- Linux Engine: `29.8.0`.
- Windows and Ubuntu clients both report client and server `29.8.0`.
- Windows context: `desktop-linux`.
- Ubuntu context: `default`, backed by Docker Desktop.
- `Ubuntu-24.04` and `docker-desktop` are running as WSL2 distributions.
- `docker run --rm hello-world` succeeded from Ubuntu.

Basic verification:

```powershell
docker version
wsl.exe -d Ubuntu-24.04 -u mars -- docker version
wsl.exe -d Ubuntu-24.04 -u mars -- docker run --rm hello-world
```

## Network state

- Clash Verge is running and listening on `127.0.0.1:7897`.
- WSL reads its host gateway dynamically from `/proc/net/route`.
- WSL `HTTPS_PROXY` currently points at the host gateway on port `7897`.
- DeepSeek from WSL returns the expected HTTP `401` without auth.
- GitHub from WSL currently fails:

  ```text
  curl: (35) OpenSSL SSL_connect: SSL_ERROR_SYSCALL
  GITHUB=000
  ```

This is the current blocking network issue. Do not interpret it as a Docker or
PATH failure. Review the Clash GitHub rule and selected proxy node, then rerun:

```powershell
wsl.exe -d Ubuntu-24.04 -u mars -- bash -lc `
  'curl -sS -o /dev/null -w "%{http_code}\n" --max-time 30 https://github.com'
```

Expected output: `200`.

## Codex state

- CLI/Desktop version: `0.166.0-alpha.5.1`.
- Provider: custom DeepSeek provider.
- Model: `deepseek-flash`.
- Authentication: configured.
- Sandbox backend: Windows `elevated`.
- Filesystem/network: restricted, approval `OnRequest`.
- MXC is unavailable on this Windows 10 host; `elevated` is the supported
  fallback.
- A direct sandbox probe succeeded:

  ```powershell
  codex sandbox -P :workspace -- cmd.exe /d /c "echo SANDBOX_WINDOWS_OK"
  ```

- `codex doctor --summary` reports 21 ok, 0 failed, 3 warnings:
  Defender exclusions are not verified; noninteractive terminal reports
  `TERM=dumb`; three thread-history rows reference missing rollouts.
- No Codex MCP servers are configured. The previous stale `node_repl`
  configuration is no longer active.
- The Codex sandbox uses its bundled PowerShell 7.6.5. A normal user shell uses
  system PowerShell 7.6.9.

Do not run persistent PATH changes from the Codex sandbox. Use a normal
PowerShell 7 session. Use an elevated PowerShell only for Machine-scope
changes.

## Hermes state

- Version: `v0.21.4 (2026.9.21)`, upstream `836b5f82`.
- Command: `/home/mars/.local/bin/hermes`.
- Provider: `deepseek`.
- Model: `deepseek-flash`.
- Base URL: `https://api.deepseek.com/v1`.
- Terminal backend: local.
- Default terminal directory: `/mnt/d/CodexApp/Project13/Git`.
- Real inference returned `HERMES_OK`.
- Hermes successfully invoked a Windows program through WSL interop.
- Core capabilities include terminal, file, browser, browser-use,
  computer_use, web search/extract, memory, skills, cron, project, todo,
  session search, TTS, and code execution.
- `hermes doctor` reports four issues: three upstream npm dependency advisory
  groups and optional full-tool credentials.
- The installation reports being behind upstream. Back up before updating.

Credentials remain local under `/home/mars/.hermes/.env`. Do not print, copy,
commit, or inspect that file.

## Git state

- Current branch: `main`.
- Use `git log -1 --oneline` for the authoritative revision.
- The current project has its existing `origin` and local `backup` remote.
- Do not copy `.git`, remote configuration, history, or the existing bare backup
  repository into a new project.
- For a new project, follow `docs/PORTABLE_INFRASTRUCTURE.md` and create a new
  repository and new remote.

## Verification evidence

Latest successful full infrastructure record:

```text
logs/last-verification.json
verified_at: 2026-09-22T19:31:59.5579235+08:00
```

The full verifier has not successfully completed since the 2026-10-30
environment changes because WSL GitHub access fails. It aborts before updating
`last-verification.json`.

Fresh checks completed on 2026-10-30:

- Windows Docker client and Linux Engine both `29.8.0`.
- Ubuntu Docker client connected to the same Engine.
- Ubuntu `hello-world` container passed.
- system PATH: 17 entries, no empty, duplicate, or missing entries at the last
  cleanup;
- user PATH: 7 entries, no empty or duplicate entries;
- `PYTHONPATH` absent;
- uv, pip, and npm caches writable;
- Python 3.14: 16 tests passed;
- Codex sandbox probe passed;
- Codex doctor: 0 failures.

## Resume commands

Start Clash Verge, then check:

```powershell
Test-NetConnection 127.0.0.1 -Port 7897

wsl.exe -d Ubuntu-24.04 -u mars -- bash -lc `
  'curl -sS -o /dev/null -w "%{http_code}\n" --max-time 30 https://github.com'
```

Check Windows tooling:

```powershell
pwsh --version
uv --version
python --version
pip --version
docker version
```

Check Docker integration:

```powershell
wsl.exe -l -v
wsl.exe -d Ubuntu-24.04 -u mars -- docker version
wsl.exe -d Ubuntu-24.04 -u mars -- docker run --rm hello-world
```

Check Python caches:

```powershell
$env:UV_CACHE_DIR
$env:PIP_CACHE_DIR
$env:NPM_CONFIG_CACHE
uv python list --only-installed
python -m pip cache dir
npm config get cache
```

Run project tests with the clean Windows Python:

```powershell
Set-Location D:\CodexApp\Project13\Git
$env:PYTHONPATH = $null
D:\Python314\python.exe -m unittest discover -s tests -v
```

Expected result: `16` tests pass.

After GitHub connectivity is fixed, run the full verification:

```powershell
& 'C:\Users\Mars\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe' `
  -NoProfile -ExecutionPolicy Bypass `
  -File 'D:\CodexApp\Project13\Git\infra\windows\04-Verify-Infrastructure.ps1'
```

Expected result: `Infrastructure verification succeeded.`

## Recommended next work

1. Fix WSL GitHub access through Clash and rerun the full infrastructure
   verifier.
2. Install `bubblewrap` in Ubuntu:

   ```bash
   sudo apt update
   sudo apt install -y bubblewrap
   ```

3. If Linux-native Codex is required, install the Codex CLI inside WSL and set
   up a separate provider credential source without copying plaintext secrets.
4. Create a project-local `.venv` with uv and keep project dependencies out of
   the global Python installation.
5. Decide whether `python3` and `py` compatibility shims are required.
   Prefer `python`, `.venv`, and `uv run` until a concrete workload requires
   them.
6. Back up Hermes, review the update plan, update it, and rerun `hermes doctor`.
7. Add CMake/Ninja only through a controlled command path or the Visual Studio
   `vcvars64.bat` developer environment.
8. When starting the new project, do not copy Git metadata or remotes. Create a
   new repository and follow `docs/PORTABLE_INFRASTRUCTURE.md`.

## New conversation protocol

1. Read this file first.
2. Run `git status --short --branch` before edits.
3. Check the current revision with `git log -1 --oneline`.
4. Recheck WSL GitHub connectivity before relying on package downloads or Git
   fetch/push through WSL.
5. Run the Python tests before changing project code.
6. Run the Hermes inference smoke test before a long Hermes workflow.
7. Keep secrets, runtime state, generated data, and logs out of Git.
8. Commit verified repository changes and sync both configured remotes.

## Do not do

- Do not restore ChemDraw or MGLTools Python 2.7 to the global PATH.
- Do not set a global `PYTHONPATH`.
- Do not use `setx PATH`; update User and Machine PATH separately while
  preserving all valid entries.
- Do not add raw MSVC `cl.exe` directories to PATH; activate the Visual Studio
  developer shell instead.
- Do not replace `C:\Users\Mars\.local\bin\uv.exe` with a shortcut to the
  WinGet package directory; direct copies are required for Codex sandbox use.
- Do not grant passwordless sudo or unrestricted Full Access merely to make an
  agent workflow succeed.
- Do not run automated `wsl --shutdown` or `wsl --terminate` on this Windows 10
  host.
- Do not copy the current `.git`, remotes, or backup repository into a new
  project.
- Do not print, copy, commit, or include API keys, OAuth tokens, SSH keys, or
  cloud credentials in a conversation or repository.
