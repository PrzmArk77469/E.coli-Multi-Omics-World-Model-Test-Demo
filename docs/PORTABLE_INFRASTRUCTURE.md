# Portable Infrastructure Guide

Last updated: 2026-09-22

## 1. Purpose

This document describes how to reproduce the verified local infrastructure in
a different project without inheriting this project's Git history, remotes,
credentials, runtime state, or data.

The portable baseline is:

```text
Windows host
  -> modern WSL2
  -> Ubuntu 24.04
  -> Node.js and Python toolchains
  -> Docker Desktop with Linux containers
  -> Clash Verge proxy for external development traffic
  -> optional Nous Research Hermes Agent
  -> a new Git repository owned by the destination project
```

Alibaba Cloud ECS, OSS, and GPU resources are planned extensions, not required
parts of the local portable baseline.

## 2. Non-negotiable Git isolation

A new project must start with a new Git repository. Do not copy the existing
`.git` directory, Git configuration, remotes, tags, branches, worktree
metadata, or bare backup repository.

Never carry these items into the new project:

- `.git/`;
- `.gitmodules`;
- local `origin`, `backup`, or other remote configuration;
- the old GitHub repository URL;
- old commits, branches, tags, hooks, or worktree metadata;
- `logs/`;
- `~/.hermes/` runtime state or credentials;
- `.env`, API keys, OAuth tokens, SSH keys, or cloud credentials.

The safest copy operation is a file-level copy that excludes `.git` and all
runtime directories from the beginning.

## 3. Placeholders

Before adapting the scripts, define the destination names:

| Placeholder | Meaning | Example |
|---|---|---|
| `<PROJECT_SLUG>` | Short identifier used in markers and firewall rules | `NewProject` |
| `<REPO_ROOT_WINDOWS>` | Windows path containing the new repository | `D:\Projects\NewProject\Git` |
| `<REPO_ROOT_WSL>` | WSL path for the same repository | `/mnt/d/Projects/NewProject/Git` |
| `<PROJECT_DATA_ROOT>` | Optional large-data root outside Git | `D:\Projects\NewProject\Data` |
| `<DISTRO_NAME>` | WSL distribution name | `Ubuntu-24.04` |
| `<LINUX_USER>` | Ubuntu user | `mars` |
| `<WSL_INSTALL_ROOT>` | WSL VHDX location | `D:\WSL\Ubuntu-24.04` |
| `<DOCKER_INSTALL_ROOT>` | Docker Desktop application location | `D:\DockerDesktop` |
| `<DOCKER_DATA_ROOT>` | Docker data location | `D:\DockerDesktopData` |
| `<PROXY_PORT>` | Clash mixed HTTP proxy port | `7897` |
| `<NEW_REPO_URL>` | Empty repository created by the destination project | `https://host/new-owner/new-repo.git` |

Windows paths map to WSL paths as follows:

```text
D:\Projects\NewProject\Git
  -> /mnt/d/Projects/NewProject/Git
```

Do not use spaces in script-facing paths unless every PowerShell, Bash, Docker,
and Git command has been retested with quoting.

## 4. Verified baseline versions

The reference machine currently verifies:

| Component | Verified value |
|---|---|
| Windows | Windows 10 Home 22H2 build 19045 |
| WSL runtime | `2.7.14` |
| Linux kernel | `6.18.33.2-microsoft-standard-WSL2` |
| Ubuntu | `24.04`, WSL2 |
| Git | `2.43.0` |
| Python | `3.12.3` |
| uv | `0.12.17` |
| nvm | `0.40.4` |
| Node.js | `v22.23.2` |
| npm | `10.9.8` |
| corepack | `0.34.6` |
| Docker Desktop | `4.91.0` |
| Docker Engine | `29.8.0` |
| Hermes Agent | `v0.21.4`, upstream `836b5f82` |
| Hermes provider | `deepseek` |
| Hermes model | `deepseek-flash` |

Pin versions in the destination project. Do not silently replace them with
`latest` during a recorded deployment.

## 5. Portable copy set

Copy only the infrastructure and repository hygiene files that the destination
project needs:

```text
infra/
  windows/
    00-Enable-Wsl2.ps1
    01-Install-Ubuntu2404.ps1
    02-Install-DockerDesktop.ps1
    03-Configure-WSL.ps1
    04-Verify-Infrastructure.ps1
  wsl/
    bootstrap-ubuntu.sh
    configure-node.sh
    configure-proxy.sh
    install-hermes.sh
    project13-proxy.bashrc

Run-Infrastructure.cmd
Resume-Infrastructure.ps1
Configure-GitRemote.ps1
docs/PORTABLE_INFRASTRUCTURE.md
.gitignore
```

The destination project may rename `project13-proxy.bashrc`. If it does, update
the corresponding filename in `configure-proxy.sh`.

Do not copy the original project's `README.md`, deployment-status files,
conversation handoff, data documentation, simulation code, data directories,
logs, or project-specific design documents unless they are intentionally
adapted for the new project.

## 6. Required path and marker adaptations

The current scripts are a working reference implementation. Before using them
in a different path or project, replace all legacy project paths and markers.

### `infra/windows/01-Install-Ubuntu2404.ps1`

Update:

- `$DistroName`;
- `$InstallRoot`;
- `$DownloadRoot`;
- `$LinuxUser`;
- pinned WSL, Ubuntu rootfs, and SHA256 values if the target versions change.

`$bootstrapPath` is derived from the repository's actual Windows location, so
it does not need a manual project-specific edit.

### `infra/windows/02-Install-DockerDesktop.ps1`

Update:

- `$InstallRoot`;
- `$DataRoot`;
- `$DistroName`;
- `$ProxyUrl`.

### `infra/windows/03-Configure-WSL.ps1`

Update `$DistroName` and adjust memory, CPU, swap, and VHD behavior for the new
machine. The reference settings are `9 GB` memory, `8` processors, and `12 GB`
swap.

### `infra/windows/04-Verify-Infrastructure.ps1`

Update:

- `$DistroName`;
- `$LinuxUser`;
- `$ProxyPort`;
- `$FirewallRuleName`;
- expected Node.js and Hermes versions when the destination project pins
  different versions.

### `infra/wsl/bootstrap-ubuntu.sh`

The script derives `REPO_ROOT` from its own location. Update package or mirror
choices only when the destination project needs different repositories.

### `infra/wsl/configure-node.sh`

The script derives `REPO_ROOT` from its own location. Update:

- `TARGET_USER`;
- `NODE_MAJOR`;
- `NODE_VERSION`;
- `NVM_VERSION`.

### `infra/wsl/configure-proxy.sh` and the proxy block

Update:

- the proxy marker text;
- the proxy block filename;
- `<PROXY_PORT>`;
- package-manager and domain-specific direct rules.

### `infra/wsl/install-hermes.sh`

The script derives `REPO_ROOT` from its own location. Re-review the official
installer URL and SHA256 before changing the pinned Hermes installer revision.

### Root launchers

`Run-Infrastructure.cmd` and `Resume-Infrastructure.ps1` resolve the repository
relative to their own location. Keep them in the repository root.

## 7. Initialize the destination repository

After copying only files, open PowerShell in the new repository:

```powershell
Set-Location <REPO_ROOT_WINDOWS>

git init -b main
git status
git remote -v
```

The first `git remote -v` must produce no output. If an old remote appears,
stop and remove the copied Git metadata before continuing.

Add and commit the portable files:

```powershell
git add .
git commit -m "Add portable infrastructure baseline"
```

Create an empty repository in the new Git hosting account, then add only that
new repository:

```powershell
git remote add origin <NEW_REPO_URL>
git remote -v
git push -u origin main
```

Do not reuse the source project's repository URL. Do not copy its local backup
repository or backup remote.

If a local rollback remote is required, create a new bare repository and new
remote for the destination project:

```powershell
git init --bare <BACKUP_REPO_WINDOWS>
git remote add backup <BACKUP_REPO_WINDOWS>
git push -u backup main
```

## 8. Installation sequence

### Phase 1: Windows and WSL features

Run PowerShell as Administrator:

```powershell
Set-Location <REPO_ROOT_WINDOWS>
.\infra\windows\00-Enable-Wsl2.ps1
```

If a reboot is required, restart Windows before continuing.

### Phase 2: Ubuntu and base packages

```powershell
.\infra\windows\01-Install-Ubuntu2404.ps1 `
  -DistroName "<DISTRO_NAME>" `
  -InstallRoot "<WSL_INSTALL_ROOT>" `
  -LinuxUser "<LINUX_USER>"
```

The script installs the pinned modern WSL runtime when absent, imports Ubuntu
24.04, creates the Linux user, writes `/etc/wsl.conf`, and runs the Ubuntu
bootstrap.

The bootstrap installs Git, Python, `uv`, build tools, SSH client, `tmux`,
archive tools, and then calls `configure-node.sh`.

Set the Linux password interactively after installation:

```powershell
wsl.exe -d <DISTRO_NAME> -u root -- passwd <LINUX_USER>
```

Never store the password in a script or repository file.

### Phase 3: WSL runtime settings

```powershell
.\infra\windows\03-Configure-WSL.ps1 -DistroName "<DISTRO_NAME>"
```

This writes `%USERPROFILE%\.wslconfig`. Do not add automated
`wsl --shutdown` or `wsl --terminate` calls on the reference Windows 10 host.

### Phase 4: Proxy and Docker

Start Clash Verge and confirm that the mixed proxy port is listening:

```powershell
Test-NetConnection 127.0.0.1 -Port <PROXY_PORT>
```

Install or configure Ubuntu shell proxy variables:

```powershell
wsl.exe -d <DISTRO_NAME> -u <LINUX_USER> -- bash <REPO_ROOT_WSL>/infra/wsl/configure-proxy.sh
```

Then install or repair Docker Desktop:

```powershell
.\infra\windows\02-Install-DockerDesktop.ps1 `
  -DistroName "<DISTRO_NAME>" `
  -InstallRoot "<DOCKER_INSTALL_ROOT>" `
  -DataRoot "<DOCKER_DATA_ROOT>"
```

Docker Desktop must use the WSL2 backend and explicit `<DISTRO_NAME>`
integration. Keep the image and container data under `<DOCKER_DATA_ROOT>`.

### Phase 5: Node.js

The bootstrap normally configures Node automatically. To repair it separately:

```powershell
wsl.exe -d <DISTRO_NAME> -u root -- bash <REPO_ROOT_WSL>/infra/wsl/configure-node.sh
```

The script maintains:

- nvm under `/home/<LINUX_USER>/.nvm`;
- a pinned default Node.js version;
- `/home/<LINUX_USER>/.nvm/current`;
- stable `/usr/local/bin/node`, `npm`, `npx`, and `corepack` links;
- nvm initialization in `.bashrc`;
- login-shell initialization through `.profile`.

The stable links are required so non-login shells, Hermes, and verification
scripts resolve Linux Node.js rather than a Windows npm shim.

### Phase 6: Hermes Agent, optional

Hermes is useful but independent of the core WSL, Node, Docker, and proxy
baseline.

```powershell
wsl.exe -d <DISTRO_NAME> -u <LINUX_USER> -- bash -lc `
  "cd <REPO_ROOT_WSL> && bash infra/wsl/install-hermes.sh"
```

The installer:

1. verifies the reviewed installer SHA256;
2. installs missing Ubuntu build and media dependencies;
3. configures the nvm-managed Node.js toolchain;
4. installs Hermes with setup skipped;
5. runs diagnostics without writing API keys.

Credentials remain local under `/home/<LINUX_USER>/.hermes/.env`. Configure
the provider interactively with `hermes setup` or `hermes model`.

## 9. Network requirements

The reference topology is:

```text
Docker Desktop
  -> http://127.0.0.1:<PROXY_PORT>

Windows applications
  -> http://127.0.0.1:<PROXY_PORT>

WSL Ubuntu
  -> http://<windows-host-gateway>:<PROXY_PORT>
```

The WSL gateway must be discovered dynamically from `/proc/net/route`. Do not
hard-code `172.x.x.x`.

Clash Verge requirements:

- mode `Rule`;
- mixed port `<PROXY_PORT>`;
- Allow LAN enabled;
- system proxy optional;
- TUN mode disabled by default for the reference stack;
- Windows Firewall inbound TCP `<PROXY_PORT>` restricted to
  `172.16.0.0/12`;
- external development services routed through the selected proxy group;
- domestic mirrors such as Aliyun routed directly.

Keep localhost, private WSL networks, Docker networks, and domestic mirrors in
`NO_PROXY`.

## 10. Logs, secrets, and data boundaries

Store runtime logs under:

```text
<REPO_ROOT_WINDOWS>\logs
```

Ignore logs and local runtime state in Git:

```gitignore
logs/*
!logs/README.md
*.log
*.pid
.cache/
.venv/
tmp/
```

Never commit:

- API keys, OAuth tokens, SSH private keys, or cloud AccessKeys;
- `~/.hermes/.env`;
- Hermes sessions, memories, browser caches, or databases;
- Docker images, layers, or container data;
- raw data, reference archives, checkpoints, or generated large artifacts;
- copied Git remotes or repository metadata.

Every generated artifact should record its source version, code commit,
configuration, container image, and random seed.

## 11. Verification

Run the complete verifier:

```powershell
Set-Location <REPO_ROOT_WINDOWS>
.\infra\windows\04-Verify-Infrastructure.ps1 `
  -DistroName "<DISTRO_NAME>" `
  -LinuxUser "<LINUX_USER>"
```

Expected core checks:

```text
WSL runtime reachable
Ubuntu running as WSL2
Git, uv, Node.js, npm, npx, and corepack available
/usr/local/bin/node resolves to the Linux Node.js executable
Docker client and server available
hello-world container runs
Clash proxy port reachable
GitHub proxy request returns HTTP 200
Aliyun direct request returns a valid HTTP response
Git remote through the proxy succeeds
Windows Firewall rule is enabled
```

Optional Hermes checks:

```powershell
wsl.exe -d <DISTRO_NAME> -u <LINUX_USER> -- bash -lc "hermes --version"
wsl.exe -d <DISTRO_NAME> -u <LINUX_USER> -- bash -lc "hermes doctor"
wsl.exe -d <DISTRO_NAME> -u <LINUX_USER> -- bash -lc `
  "hermes -z 'Reply with exactly HERMES_OK and nothing else.'"
```

Expected inference output:

```text
HERMES_OK
```

## 12. New-repository acceptance checks

Before treating the migration as complete, verify:

```powershell
git remote -v
git log --all --oneline
git rev-list --all --count
```

Acceptance conditions:

- `origin` points only to the newly created destination repository;
- no source-project remote is present;
- the history contains only the destination project's commits;
- no copied `.git` metadata, old tags, or old branches remain;
- no credential, log, session, cache, or large data file is staged;
- the infrastructure verifier succeeds after path substitution;
- the destination project can be cloned from its new repository and reproduced
  from the portable guide.

## 13. Recovery rules

1. Read the newest log under `logs/` and identify the first failing command.
2. Re-run the failed idempotent script after correcting the path or dependency.
3. Do not rewrite or delete external data without explicit approval.
4. Before unregistering a WSL distribution, export it:

   ```powershell
   wsl.exe --export <DISTRO_NAME> <WSL_BACKUP_TAR>
   ```

5. Do not run automated `wsl --shutdown` or `wsl --terminate` on the reference
   Windows 10 host.
6. Docker Desktop can be reinstalled without deleting `<DOCKER_DATA_ROOT>`.
7. Re-run `install-hermes.sh` when Hermes code is missing or damaged. Restore
   `~/.hermes` only when sessions, memory, or configuration are also affected.
8. If the destination repository is wrong, stop before committing or pushing.
   Correct the remote first; never push new-project history to the source
   project's repository.

## 14. Final handoff checklist

- [ ] The destination repository was initialized from files, not copied Git
      history.
- [ ] No source-project remote, backup, branches, or tags are present.
- [ ] All legacy path and project markers were replaced.
- [ ] WSL2 and Ubuntu are installed and verified.
- [ ] Git, Python, `uv`, nvm, Node.js, npm, npx, and corepack pass checks.
- [ ] Docker Desktop and Ubuntu integration pass `hello-world`.
- [ ] Clash proxy and Windows Firewall rules are active.
- [ ] Node.js is visible to non-login shells and Hermes.
- [ ] Hermes diagnostics and inference pass when Hermes is required.
- [ ] Logs, credentials, runtime state, and large data remain outside Git.
- [ ] `git remote -v` shows only the new repository.
- [ ] The new project is pushed to a newly created repository.
