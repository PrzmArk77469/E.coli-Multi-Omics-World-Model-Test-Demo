# New Conversation Context

## Read these first

1. `README.md`
2. `docs/DEPLOYMENT_STATUS.md`
3. `docs/INFRASTRUCTURE.md`
4. `docs/LOGGING_AND_ROLLBACK.md`

## Current machine layout

| Item | Path |
|---|---|
| Repository | `D:\CodexApp\Project13\Git` |
| Existing data tree | `D:\CodexApp\Project13\EcoliOmics` |
| WSL distro | `Ubuntu-24.04` |
| WSL VHDX root | `D:\WSL\Ubuntu-24.04` |
| Ubuntu rootfs archive | `D:\WSL\Downloads\ubuntu-base-24.04.5-base-amd64.tar.gz` |
| Docker Desktop | `D:\DockerDesktop` |
| Docker WSL data | `D:\DockerDesktopData` |
| Logs | `D:\CodexApp\Project13\Git\logs` |
| Local Git backup | `D:\CodexApp\Project13\GitBackup.git` |

## Current state

- WSL2 and VirtualMachinePlatform are enabled but require a Windows reboot.
- The Ubuntu rootfs is downloaded and SHA256-verified.
- Docker Desktop is installed on D: and configured with its WSL data root on
  D:.
- The repository has an initial commit and a local `backup` remote.
- No external Git `origin` is configured yet.

## Resume command

After the Windows reboot, run this from an elevated PowerShell:

```powershell
& D:\CodexApp\Project13\Git\Resume-Infrastructure.ps1
```

Then set the Linux password:

```powershell
wsl.exe -d Ubuntu-24.04 -u root -- passwd mars
```

## Git remote

When the repository URL is known:

```powershell
& D:\CodexApp\Project13\Git\Configure-GitRemote.ps1 -RemoteUrl '<repository-url>'
```

## Do not do

- Do not commit `D:\CodexApp\Project13\EcoliOmics\raw`.
- Do not store SSH keys, cloud credentials, or API tokens in the repository.
- Do not unregister `Ubuntu-24.04` before exporting a backup.

