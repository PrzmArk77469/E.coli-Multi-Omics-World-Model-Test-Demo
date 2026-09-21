# WSL2 and Ubuntu 24.04 on D:

## Constraints

- Windows remains at its current version; no Windows upgrade is performed.
- WSL2 and VirtualMachinePlatform require administrator privileges.
- Enabling the Windows features can require one reboot.
- Ubuntu is imported explicitly into D: instead of using the default C: store.
- Docker Desktop's installation entry points may use C:, but its image and WSL
  data roots are configured on D:.

## Scripts

Run from an elevated PowerShell:

```powershell
Set-Location D:\CodexApp\Project13\Git
.\infra\windows\00-Enable-Wsl2.ps1
```

If a reboot is required, restart Windows and then run:

```powershell
Set-Location D:\CodexApp\Project13\Git
.\infra\windows\01-Install-Ubuntu2404.ps1
.\infra\windows\02-Install-DockerDesktop.ps1
```

The Ubuntu bootstrap can also be rerun safely from PowerShell:

```powershell
wsl.exe -d Ubuntu-24.04 -u root -- bash /mnt/d/CodexApp/Project13/Git/infra/wsl/bootstrap-ubuntu.sh
```

## User password

The Linux user is created during import. Set its password before using `sudo`
inside the distro:

```powershell
wsl.exe -d Ubuntu-24.04 -u root -- passwd mars
```

## Verification

```powershell
wsl.exe -l -v
wsl.exe -d Ubuntu-24.04 -- uname -a
wsl.exe -d Ubuntu-24.04 -- docker info
```

The expected WSL state is `Running` and version `2`.

