# Infrastructure

## Target topology

```text
Windows Codex
  -> WSL2 Ubuntu 24.04 on D:
  -> Docker Desktop data on D:
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
- Memory limit: 9 GB
- Swap: 12 GB
- Processor limit: 8
- Windows drive access: `/mnt/d`

The repository can be accessed from Ubuntu as
`/mnt/d/CodexApp/Project13/Git`. For Python environments and many-small-file
workloads, use a clone inside the Linux filesystem and keep large data
read-only through `/mnt/d`.

## Container policy

- Use Docker Desktop with the WSL2 backend.
- Pin experiment images by Git SHA or digest.
- Do not use mutable `latest` tags for recorded experiments.
- Keep image storage on `D:\DockerDesktopData`.

## Cloud policy

- Start with a CPU ECS control plane and private OSS buckets.
- Add one on-demand GPU ECS only after a CPU baseline exists.
- Stop or release GPU instances after every job.
- Prefer RAM roles and temporary credentials over long-lived AccessKeys.
- Access private services through SSH or a private network, never a public
  Jupyter or database port.
