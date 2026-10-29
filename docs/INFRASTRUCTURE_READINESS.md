# Infrastructure Readiness Assessment

Last updated: 2026-10-29

## 1. Scope

This assessment covers the local infrastructure used by Codex and the
DeepSeek-backed Hermes Agent on the current Windows 10 host. It focuses on
PowerShell, Python, WSL, Docker, network access, hardware limits, credentials,
and the permissions needed for more varied local work.

"DeepSeek Harness" is interpreted here as the installed Hermes Agent configured
with the DeepSeek provider and `deepseek-flash` model. Codex is also configured
to use a custom DeepSeek provider.

The goal is not to give one agent unrestricted administrator access. The goal
is to expose the required local capabilities through explicit, auditable,
least-privilege interfaces so both agents can operate reliably.

## 2. Executive summary

The local baseline remains operational, but it is not yet a unified
all-resource execution environment.

| Area | State | Summary |
|---|---|---|
| Windows Codex sandbox | Usable | `elevated` sandbox provisioning is complete and a command ran successfully |
| Windows MXC sandbox | Unavailable | Not supported on this Windows 10 host |
| PowerShell 7 | Degraded | `pwsh` is available only from the Codex runtime cache, not as a system tool |
| Windows Python | High risk | Default `python` is a 32-bit Python 2.7 installation from MGLTools |
| Windows Python isolation | Partial | Python 3.14 venv creation works, but global package and `PYTHONPATH` pollution remains |
| WSL Python | Good baseline | Python 3.12.3 and uv 0.12.17 work; project environments still need to be created |
| WSL Codex sandbox | Not ready | `bubblewrap` and the Codex CLI are missing inside WSL |
| Node.js | Good | WSL has pinned Node.js 22.23.2; Windows has Node.js 24.19.0 |
| Docker | Offline | Docker Desktop and its Linux engine are stopped; WSL integration is unavailable |
| WSL network | Good | Clash proxy works; GitHub reached HTTP 200 and DeepSeek returned an expected HTTP 401 |
| Hermes inference | Operational | Real inference and Windows interop both returned the expected output |
| Hermes maintenance | Degraded | The installation is behind upstream, dependency advisories exist, and `doctor` reports four issues |
| Credentials | Critical | A provider secret is stored in user configuration readable by the Windows sandbox users |
| Compute capacity | Constrained | 16 GB RAM, 8C/16T CPU, 9 GB and 8 vCPU assigned to WSL, no CUDA-capable GPU |

## 3. Verified host inventory

### Windows

| Item | Observed value |
|---|---|
| OS | Windows 10 Home China 22H2, build 19045 |
| CPU | AMD Ryzen 7 4800U, 8 cores / 16 logical processors |
| RAM | 16 GB |
| GPU | AMD Radeon integrated graphics, no NVIDIA/CUDA device |
| Disks | C: 91.4 GB free, D: 100.0 GB free, G: 302.4 GB free |
| Codex | `0.165.0-alpha.1.2` |
| PowerShell | Windows PowerShell `5.1.19041.6456`; bundled pwsh `7.6.5` |
| Python 3 | `D:\Python314\python.exe`, Python `3.14.5`, pip `26.1.1` |
| Default `python` | `D:\AutodockSuits\MGLTools\python.exe`, Python `2.7.11`, 32-bit |
| Node.js | `v24.19.0`; npm `12.2.0` |
| Docker Desktop | `4.91.0`; client available, engine stopped |
| Visual Studio | Visual Studio Professional 2019 with MSVC, CMake, and Ninja components |
| Other tools | Git `2.56.0.2`, Java 8 first on PATH, .NET SDK `5.0.416`, VS Code |

### Ubuntu WSL

| Item | Observed value |
|---|---|
| Distro | Ubuntu 24.04, WSL2 |
| Kernel | `6.18.33.2-microsoft-standard-WSL2` |
| CPU allocation | 8 logical processors |
| Memory allocation | 9 GB configured; 8.7 GiB visible |
| Swap | 12 GB |
| Root filesystem | 251 GB virtual size, 234 GB available |
| Python | `/usr/bin/python3`, Python `3.12.3` |
| uv | `/usr/local/bin/uv`, `0.12.17` |
| Node.js | `/usr/local/bin/node`, `v22.23.2` |
| npm | `10.9.8` |
| GCC/G++ | `13.3.0` |
| Make | `4.3` |
| ffmpeg | `6.1.1` |
| CMake/Ninja | Missing |
| R | Missing |
| PowerShell | Linux `pwsh` missing; Windows `pwsh.exe` reachable through interop |
| Codex CLI | Missing |
| bubblewrap | Missing |
| Hermes | `v0.21.4`, upstream `836b5f82` |

## 4. Priority findings

### P0: Provider credentials are overexposed

The user-level Codex configuration contains a literal bearer token for the
custom provider. Codex auth storage also contains an API key. Both files inherit
read access for the `CodexSandboxUsers` local group.

This means a sandboxed process can read credential material that it does not
need in order to execute project commands. The audit itself demonstrated that
the current sandbox can read the user-level Codex configuration.

Required response:

1. Rotate the exposed provider credential.
2. Replace the literal token with a command-backed credential source or an
   environment value supplied only by the trusted launcher.
3. Deny sandbox read access to Codex configuration, auth storage, `.env` files,
   SSH keys, and cloud credential directories.
4. Keep provider configuration in user-level config. Project-local Codex config
   is not the correct place for secrets or provider definitions.

Do not copy the current Codex configuration into another project as-is.

### P1: Windows Python resolution is unsafe

The command name `python` resolves to MGLTools Python 2.7.11, 32-bit. The
installed Python 3.14.5 is later on `PATH`; `pip` resolves to Python 3.14.

Observed problems:

- `python --version` reports Python 2.7.11.
- `python3` resolves to an unusable Windows Store alias.
- `py -0p` reports no registered Python installations.
- `PYTHONPATH` globally points at ChemDraw's ChemScript library and is injected
  into every Python 3.14 process.
- `uv` is not installed on Windows.
- `pyarrow` and `polars` are missing from the global Python 3.14 environment.

Python 3.14 itself is functional. NumPy, pandas, SciPy, matplotlib, and
scikit-learn import successfully, and a clean virtual environment can be
created. The issue is interpreter selection and isolation, not a missing
interpreter.

Recommended layout:

- Keep the 32-bit MGLTools Python installation for AutoDock/MGLTools only.
- Do not put MGLTools before modern Python on the normal development `PATH`.
- Install uv on Windows.
- Use a project-local `.venv` with a pinned Python version, preferably a
  well-supported scientific Python version such as 3.12 or 3.13.
- Invoke `.venv\Scripts\python.exe` explicitly in scripts.
- Remove the global ChemDraw `PYTHONPATH`; provide ChemDraw paths only in the
  specific environment that needs them.
- Install optional data libraries such as pyarrow and polars in the project
  environment, not globally.
- Prefer WSL Python plus uv for Linux-native scientific and bioinformatics
  workloads.

### P1: PowerShell 7 is not a system tool

`pwsh` currently resolves to:

```text
C:\Users\Mars\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe
```

That executable belongs to the Codex runtime cache and can move or disappear
when Codex is updated. It is not appropriate for durable user scripts,
scheduled tasks, or handoff to Hermes.

Windows PowerShell 5.1 is installed, but it is a legacy compatibility shell.

Required response:

- Install current PowerShell 7 as a machine-level application.
- Pin and record the installed version.
- Prefix Codex/Hermes helper scripts with an explicit `pwsh.exe` path check.
- Keep Windows PowerShell 5.1 only for legacy modules and Windows-specific
  administration where required.
- Test scripts in both shells when compatibility is claimed.

### P1: Codex cannot yet run as a Linux-native agent in WSL

Codex on Linux/WSL2 requires the Linux sandbox implementation. Bubblewrap is
not installed, and no Codex CLI exists in Ubuntu.

Required response:

- Install `bubblewrap` in Ubuntu.
- Confirm unprivileged user namespaces continue to work.
- Install the Codex CLI inside WSL if Linux-native Codex sessions are required.
- Keep Windows-native Codex for Windows application and service work.
- Keep Linux-native Codex for Docker, Linux compilers, bioinformatics tools, and
  repositories stored on the Linux filesystem.
- Do not keep many-small-file repositories primarily under `/mnt/d`; use the
  Ubuntu filesystem for build and package-manager workloads.

### P1: Docker is installed but not operational

The Docker client is `29.8.0`, but the Linux engine pipe is absent. Docker
Desktop is not running, and Ubuntu reports that WSL integration is unavailable.

Hermes `doctor` marks Docker as available because the client executable exists.
That check does not prove that the daemon can execute containers.

Required response:

- Start Docker Desktop before container work.
- Verify Docker Desktop integration for Ubuntu.
- Run `docker version` from both Windows and Ubuntu, not only `docker --version`.
- Run a pinned `hello-world` smoke test.
- Keep an explicit stopped/running health check in agent preflight scripts.

### P1: The Codex `node_repl` MCP server points at a stale runtime

The user-level Codex configuration points `node_repl` to runtime directory
`1fb7137c46617d50`, which no longer exists. The current installed runtime is
`e8c74e7ee9bd567e`, and its `node_repl.exe` is present.

Consequences:

- JavaScript REPL and browser-related MCP startup can fail.
- Codex `doctor` reports the MCP server as unresolved.

Required response:

- Restart or update Codex so the application regenerates its managed MCP
  configuration.
- Prefer application-managed runtime paths over manually pinned cache paths.
- Re-run `codex doctor` after the update and verify `node_repl` is resolvable.

### P2: Windows native build tools exist but are not on PATH

Visual Studio 2019 Professional contains:

- MSVC `14.29.30133`;
- CMake;
- Ninja;
- `vcvars64.bat`.

However, `cl`, `cmake`, and `ninja` are not directly available in a normal Codex
shell.

Required response:

- Provide a small Windows developer-shell wrapper that loads `vcvars64.bat`.
- Use that wrapper for native Python builds, Node native modules, Rust/C++
  builds, and CMake projects.
- Prefer WSL build-essential for Linux projects.
- Install standalone CMake/Ninja only if a stable cross-project PATH is needed.

### P2: Toolchain versions are fragmented

- Windows Node.js is `24.19.0`; WSL Node.js is `22.23.2`.
- Java 8 appears before the installed JDK 21 on Windows `PATH`.
- .NET SDK is `5.0.416`, which is old for current development work.
- R is absent from both environments.
- PowerShell is absent from WSL.
- ffmpeg is present in WSL but absent as a normal Windows command.

These are not immediate blockers, but agents should use explicit versioned
launchers rather than generic command names. Project documentation should state
which runtime owns each workload.

### P2: Hermes is operational but stale and over-privileged for its current value

Hermes inference returned `HERMES_OK`, and its terminal tool successfully ran a
Windows command through WSL interop.

Current warnings:

- `hermes doctor` reports the installation is far behind upstream.
- Browser, web, and TUI dependency trees have high-severity npm advisories.
- `hermes update --plan` showed no service changes but also no explicit target
  revision, so the update needs review rather than blind execution.
- SQLite `3.45.1` has a WAL-reset advisory. Hermes currently uses rollback
  journal mode.
- Skills Hub is not initialized.
- Several optional tools lack credentials or dependencies.

Hermes runs as the normal `mars` user with the local terminal backend. It can
reach the Windows host through WSL interop. This is useful but broad. The user
has password-required sudo, so Hermes cannot silently perform root operations.

Before updating:

1. Run `hermes backup`.
2. Review `hermes update --plan`.
3. Update in a controlled maintenance window.
4. Re-run `hermes doctor`.
5. Re-test inference, terminal, Docker, and browser tools.

For stronger isolation, run Hermes as a dedicated Linux user with explicit
group access to project and data directories instead of using the primary user.

### P2: Compute capacity cannot cover every workload concurrently

The host has 16 logical CPUs and 16 GB RAM. WSL is limited to 8 logical CPUs,
9 GB RAM, and 12 GB swap. Docker Desktop competes for the same host CPU and
memory even when its containers run in a separate WSL2 backend.

The GPU is an AMD integrated device. There is no NVIDIA driver, CUDA runtime, or
supported local accelerator path for mainstream model training.

Recommended resource profiles:

| Profile | WSL memory | WSL processors | Intended use |
|---|---:|---:|---|
| Light | 5-6 GB | 6-8 | Windows Codex, Hermes, editing, light tests |
| Analysis | 8 GB | 10-12 | Python/R analysis, containers, medium builds |
| Heavy | 10-11 GB | 12-16 | One exclusive CPU-heavy job; expect Windows memory pressure |

Do not run Windows builds, Docker containers, WSL scientific workloads, and
local LLM inference simultaneously on this machine.

Use:

- D: for active Windows projects and Docker data;
- G: for large archival/removable datasets;
- the Ubuntu ext4 filesystem for Linux build trees and package caches;
- remote GPU infrastructure for CUDA training or large-model inference.

### P2: Codex command rules have become a large one-off allowlist

`~/.codex/rules/default.rules` is about 48 KB and contains many highly specific
historical commands. Some rules are broad, including generic
`Invoke-WebRequest` and `curl.exe -sS` prefixes.

This is difficult to audit and can make future approvals inconsistent.

Recommended response:

- Replace one-off command approvals with a small set of stable prefix rules.
- Use permission profiles for filesystem and network scope.
- Keep destructive, credential, privilege, and network commands under explicit
  review.
- Review and version rules like infrastructure code.

### P3: Codex operational maintenance

`codex doctor` currently reports:

- the desktop application has an update available;
- Defender exclusions for signed Codex executables are not verified;
- three thread database issues involving missing or stale rollout records;
- `node_repl` has a stale executable path.

These do not prevent current inference, but should be resolved before relying on
long-lived agent history, JavaScript REPL tools, or browser automation.

## 5. Current resource access matrix

| Resource | Codex on Windows | Codex in WSL | Hermes in WSL |
|---|---|---|---|
| Windows files | Yes, read broadly; write only approved roots | Through `/mnt`, if launched in WSL | Through `/mnt` and Windows interop |
| Linux files | Through `wsl.exe`, subject to sandbox | Native, subject to Linux sandbox | Native |
| Windows executables | Native | Through WSL interop | Through WSL interop |
| Linux executables | Through `wsl.exe` | Native | Native |
| PowerShell | Yes, currently bundled pwsh or 5.1 | Missing | Can call `pwsh.exe` through interop |
| Python | Wrong default; explicit 3.14 path works | 3.12 + uv works, project envs needed | 3.12, subject to Hermes environment |
| Docker | Client only; engine stopped | Client only; integration unavailable | Client only; integration unavailable |
| CPU/RAM | Available | Limited by `.wslconfig` | Limited by `.wslconfig` |
| GPU | Integrated AMD only | No CUDA device | No CUDA device |
| Network | Disabled by the current sandbox profile | Proxy verified | Proxy verified |
| Administrator/root | Requires approval and UAC elevation | Requires root invocation | Requires interactive sudo password |
| Credentials | Currently overexposed | Must not duplicate | Must not duplicate |

## 6. Target operating model

The safest way to let both Codex and Hermes use broad local resources is a
shared capability layer rather than granting unrestricted host access.

### Execution planes

1. **Windows user plane**
   - Codex native sandbox.
   - PowerShell 7 and Windows PowerShell 5.1.
   - Windows applications, Visual Studio tools, drives, and GUI automation.
   - Writes limited to project roots and explicitly approved data roots.

2. **WSL Linux plane**
   - Ubuntu 24.04, Python/uv, Node, C/C++, R if required.
   - Docker client and container workflows.
   - Hermes local terminal.
   - Linux sandbox using bubblewrap.

3. **Privileged operations plane**
   - A small set of reviewed scripts for WSL startup, Docker Desktop startup,
     service control, package installation, firewall changes, and system
     updates.
   - Human approval for elevation or a brokered, whitelisted local service.
   - Never expose a generic passwordless root shell to either agent.

4. **Accelerated compute plane**
   - Remote GPU service for CUDA workloads.
   - Transfer only approved datasets and publish results back through a
     controlled artifact path.

### Shared local capability gateway

For both agents to use the same resources predictably, create a local MCP or
command gateway with narrow tools such as:

- `files.list/read/write` limited to configured roots;
- `wsl.exec` limited to `Ubuntu-24.04` and an approved user;
- `docker.status/start/list/run` with allowlisted project images;
- `windows.process.status/start/stop` for named applications;
- `hardware.status` for CPU, RAM, disk, WSL, and GPU state;
- `artifact.publish` for approved result directories.

The gateway should:

- reject arbitrary root commands;
- log caller, arguments, result, duration, and approval source;
- use separate short-lived credentials for each agent;
- expose an explicit read-only mode;
- fail closed when policy or audit logging is unavailable.

## 7. Preparation plan

### Phase 0: Security baseline

1. Rotate the DeepSeek/API credential currently present in user configuration.
2. Replace literal secret storage with a command-backed credential provider.
3. Restrict reads of `C:\Users\Mars\.codex\config.toml`, `auth.json`, `.env`
   files, and credential directories from `CodexSandboxUsers`.
4. Add deny-read rules for secret patterns.
5. Clean and minimize `~/.codex/rules/default.rules`.
6. Do not grant passwordless sudo to Codex or Hermes.

### Phase 1: Stable Windows tools

1. Install PowerShell 7 system-wide and pin its version.
2. Install uv for Windows.
3. Create a modern Python interpreter launcher strategy.
4. Remove global ChemDraw `PYTHONPATH`.
5. Keep MGLTools Python 2.7 isolated from normal development.
6. Add a developer-shell wrapper for VS 2019 MSVC, CMake, and Ninja.
7. Optionally upgrade to current Visual Studio Build Tools and .NET SDK for new
   native projects.

### Phase 2: WSL and containers

1. Install `bubblewrap` in Ubuntu.
2. Install Codex CLI in WSL only if Linux-native Codex sessions are required.
3. Add CMake/Ninja and R packages if those workloads are planned.
4. Start Docker Desktop and enable Ubuntu integration.
5. Verify Docker client, server, and `hello-world` from both environments.
6. Add a preflight health check that distinguishes installed clients from
   running services.

### Phase 3: Agent configuration

1. Repair or regenerate the Codex `node_repl` MCP configuration.
2. Create reusable Codex permission profiles:
   - `read-audit`: read-only;
   - `project-edit`: workspace writes only;
   - `data-read`: project plus approved data roots;
   - `network-research`: scoped domain allowlist;
   - `host-ops`: only the capability gateway, never unrestricted host access.
3. Configure Hermes with the same explicit data and operation boundaries.
4. Use a dedicated low-privilege Linux account for long-running Hermes work.
5. Put scheduled/background tasks under systemd or Windows Task Scheduler with
   fixed commands, not an always-running privileged shell.

### Phase 4: Compute and observability

1. Add light/analysis/heavy WSL profiles for different workloads.
2. Monitor memory, disk, Docker, WSL, and Hermes health.
3. Enable Codex OTel only when a controlled collector is available.
4. Route large-model and CUDA work to remote GPU infrastructure.
5. Record runtime, dataset, model, container, and seed provenance for every
   generated artifact.

## 8. Acceptance criteria

The environment is ready for broad local work when all of the following pass:

```powershell
Get-Command pwsh
pwsh --version
pwsh -NoProfile -Command '$PSVersionTable.PSVersion'

Get-Command uv
uv --version
D:\Python314\python.exe --version
python --version
py -0p

codex doctor
codex sandbox -P :workspace -- cmd.exe /d /c "echo CODEX_SANDBOX_OK"

wsl.exe -d Ubuntu-24.04 -u mars -- bash -lc "command -v bwrap"
wsl.exe -d Ubuntu-24.04 -u mars -- bash -lc "command -v codex"
wsl.exe -d Ubuntu-24.04 -u mars -- bash -lc "docker version"
wsl.exe -d Ubuntu-24.04 -u mars -- bash -lc "hermes doctor"
```

Expected conditions:

- `python` no longer silently selects MGLTools Python 2.7.
- `py -0p` lists the intended modern interpreter, or the project explicitly uses
  uv-managed interpreters instead.
- PowerShell 7 resolves from a stable machine installation.
- Codex sandbox and WSL sandbox both execute a test command.
- Docker reports both client and server versions.
- Hermes inference and terminal interop still pass.
- Sandboxed commands cannot read plaintext provider credentials.
- Both agents report which workspace and data roots they can access.

## 9. Official Codex references

- [Agent approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Sandboxing](https://learn.chatgpt.com/docs/sandboxing)
- [Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox)
- [WSL](https://learn.chatgpt.com/docs/windows/wsl)
- [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
