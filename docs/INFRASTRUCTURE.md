# Infrastructure

## Target topology

```text
Windows Codex
  -> WSL2 Ubuntu 24.04 on D:
  -> Docker Desktop data on D:
  -> Nous Research Hermes Agent under /home/mars/.hermes
  -> Clash Verge proxy for Docker Hub, GitHub, and release assets
  -> GitHub/Codeup source repository
  -> Alibaba Cloud CPU ECS control plane
  -> private OSS data and artifact bucket
  -> on-demand GPU ECS worker
```

## Local paths

| Component | Path |
|---|---|
| Git repository | `D:\CodexApp\Project13\Git` |
| WSL VHDX | `D:\WSL\Ubuntu-24.04` |
| WSL rootfs download | `D:\WSL\Downloads` |
| Modern WSL MSI | `D:\WSL\Downloads\wsl.2.7.14.0.x64.msi` |
| Docker Desktop install | `D:\DockerDesktop` |
| Docker data | `D:\DockerDesktopData` |
| Deployment logs | `D:\CodexApp\Project13\Git\logs` |

Windows application registration and a small per-user settings file may still
live on C:. Docker Desktop is installed in per-user mode with its application
path and WSL data root configured on D:. The large WSL disks, Ubuntu
filesystem, Docker image store, and project artifacts are kept on D:.

## WSL design

- Distro name: `Ubuntu-24.04`
- Linux user: `mars`
- WSL version: 2
- Microsoft WSL runtime: `2.7.14`
- Linux kernel: `6.18.33.2-microsoft-standard-WSL2`
- Ubuntu: `24.04`
- Memory limit: 9 GB
- Swap: 12 GB
- Processor limit: 8
- Windows drive access: `/mnt/d`

The repository can be accessed from Ubuntu as
`/mnt/d/CodexApp/Project13/Git`. For Python environments and many-small-file
workloads, use a clone inside the Linux filesystem and keep large data
read-only through `/mnt/d`.

The Ubuntu bootstrap uses a two-stage APT bootstrap. It first uses the Aliyun
HTTP mirror only to install `ca-certificates`, then switches to the Aliyun
HTTPS mirror. This is required because the Ubuntu Base rootfs initially has no
trusted CA bundle.

## Container policy

- Use Docker Desktop with the WSL2 backend.
- Docker Desktop version: `4.91.0`; Linux Engine: `29.8.0`.
- Enable integration explicitly for `Ubuntu-24.04`.
- Use the local Clash Verge proxy at `http://127.0.0.1:7897` for registry
  access when direct Docker Hub access is unavailable.
- Pin experiment images by Git SHA or digest.
- Do not use mutable `latest` tags for recorded experiments.
- Keep image storage on `D:\DockerDesktopData`.

## Agent layer

- Use the official Nous Research Hermes Agent installed in `Ubuntu-24.04`.
- Command: `/home/mars/.local/bin/hermes`.
- Code: `/home/mars/.hermes/hermes-agent`.
- Configuration and local credentials: `/home/mars/.hermes/`.
- Installation and refresh: `infra/wsl/install-hermes.sh`.
- Installer source: `https://hermes-agent.nousresearch.com/install.sh`.
- Reviewed installer SHA256:
  `00f9080c6452bf87f03ef2fffb4b2c23b9f43f946aaae956e4c547d17e310b22`.
- Active inference provider: `deepseek`.
- Active model: `deepseek-flash`.
- API base URL: `https://api.deepseek.com/v1`.
- Credentials remain local in `/home/mars/.hermes/.env` and are excluded from
  Git and documentation.
- Hermes terminal commands default to
  `/mnt/d/CodexApp/Project13/Git`.
- Hermes is an orchestration client, not the authority for scientific state,
  provenance, container pins, or cloud credentials.

## Network policy

- Local host traffic and private ranges must remain direct.
- Docker Hub, GitHub release assets, GHCR, and common public model/container
  registries may use the proxy.
- Domestic Ubuntu, PyPI, and Alibaba Cloud mirrors should remain direct.
- Exact Clash rules and Docker settings are in `docs/NETWORK_AND_PROXY.md`.
- WSL proxy variables are installed by `infra/wsl/configure-proxy.sh`.
- Windows Firewall permits only private WSL sources to reach Clash port
  `7897`; system proxy and TUN mode are not part of the required path.

## Cloud policy

- Start with a CPU ECS control plane and private OSS buckets.
- Add one on-demand GPU ECS only after a CPU baseline exists.
- Stop or release GPU instances after every job.
- Prefer RAM roles and temporary credentials over long-lived AccessKeys.
- Access private services through SSH or a private network, never a public
  Jupyter or database port.
