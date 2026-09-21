# Deployment Status

Last updated: 2026-09-21 16:15 +08:00

## Completed

- Created the Git repository skeleton at `D:\CodexApp\Project13\Git`.
- Added `.gitignore`, `.gitattributes`, `README.md`, `AGENTS.md`, and
  infrastructure documentation.
- Copied project documents, scripts, registry files, small metadata manifests,
  and visualizations into the repository.
- Enabled the Windows features `Microsoft-Windows-Subsystem-Linux` and
  `VirtualMachinePlatform`.
- Downloaded Ubuntu Base 24.04.5 to `D:\WSL\Downloads` and verified SHA256
  `e77b6f10c2590cef872b33ee9f635a0e3fd1f57fb074c0e52b5c7f56147a0c86`.
- Downloaded Docker Desktop to `D:\DockerDesktopDownloads`; Authenticode
  signature verification succeeded.
- Installed Docker Desktop to `D:\DockerDesktop`.
- Configured Docker WSL data root as `D:\DockerDesktopData`.
- Created the initial Git commit
  `dc7a5a1510acfac4df9b0a532c5e635bb1e4972f`.
- Pushed `main` to the local rollback remote
  `D:\CodexApp\Project13\GitBackup.git`.

## Pending Windows reboot

Windows returned DISM exit code `3010`. WSL2 cannot be imported until the
computer restarts.

After restart, run the following from an elevated PowerShell:

```powershell
Set-Location D:\CodexApp\Project13\Git
.\infra\windows\01-Install-Ubuntu2404.ps1
.\infra\windows\03-Configure-WSL.ps1
.\infra\windows\02-Install-DockerDesktop.ps1
.\infra\windows\04-Verify-Infrastructure.ps1
```

Then set the Linux password:

```powershell
wsl.exe -d Ubuntu-24.04 -u root -- passwd mars
```

## Git remote

- Local branch: `main`
- Local rollback remote: `backup` at
  `D:\CodexApp\Project13\GitBackup.git`
- External `origin`: not configured because no repository URL or account was
  supplied.

Configure the external remote with:

```powershell
git remote add origin <repository-url>
git push -u origin main
```

## Required user decisions

- Provide the external Git repository URL.
- Restart Windows when convenient to complete WSL2 import.
- Decide whether to mirror GitHub to Alibaba Cloud Codeup for mainland ECS
  access.
