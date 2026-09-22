# New Conversation Context

## Read these first

1. `README.md`
2. `docs/SYSTEM_ARCHITECTURE.md`
3. `docs/DEPLOYMENT_STATUS.md`
4. `docs/INFRASTRUCTURE.md`
5. `docs/LOGGING_AND_ROLLBACK.md`
6. `docs/NETWORK_AND_PROXY.md`
7. `docs/CONDITION_MAPPING.md`
8. `docs/SYNTHETIC_CONDITIONS.md`

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
| Logs | `D:\CodexApp\Project13\Git\logs` |
| Local Git backup | `D:\CodexApp\Project13\GitBackup.git` |

## Current state

- Windows remains Windows 10 Home 22H2 build 19045; no Windows upgrade was
  performed.
- Microsoft WSL runtime `2.7.14` is installed and uses Linux kernel
  `6.18.33.2-microsoft-standard-WSL2`.
- Ubuntu `24.04` is installed as `Ubuntu-24.04`, running as WSL2.
- The Linux user is `mars`; its password has been set and is intentionally not
  stored in this repository.
- Git, Python, build tools, `uv 0.12.17`, and the base developer packages are
  installed in Ubuntu.
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
- The repository is connected to
  `https://github.com/PrzmArk77469/E.coli-Multi-Omics-World-Model-Test-Demo.git`
  as `origin`.
- A local rollback remote named `backup` points to
  `D:\CodexApp\Project13\GitBackup.git`.
- The latest verification is recorded in `logs/last-verification.json`.
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

## Resume command

Start Clash Verge so port `7897` is listening, then run:

```powershell
& D:\CodexApp\Project13\Git\Run-Infrastructure.cmd
```

The launcher self-elevates and bypasses the execution-policy restriction. If
the infrastructure is already running, the preferred direct checks are:

```powershell
& 'C:\Program Files\WSL\wsl.exe' -l -v
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -- git --version
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -- uv --version
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -- docker version
& 'C:\Users\Mars\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe' -NoProfile -ExecutionPolicy Bypass -File D:\CodexApp\Project13\Git\infra\windows\04-Verify-Infrastructure.ps1
```

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
