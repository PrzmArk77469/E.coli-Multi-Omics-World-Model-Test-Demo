# WSL2 and Ubuntu 24.04 on D:

## Constraints

- Windows remains at its current version; no Windows upgrade is performed.
- WSL2 and VirtualMachinePlatform require administrator privileges.
- Enabling the Windows features can require one reboot.
- Ubuntu is imported explicitly into D: instead of using the default C: store.
- Docker Desktop's installation entry points may use C:, but its image and WSL
  data roots are configured on D:.
- Docker Desktop 4.91 requires a modern WSL runtime that supports `wsl
  --version`; the legacy inbox runtime is not sufficient.

## Scripts

The normal entry point is the self-elevating launcher:

```cmd
D:\CodexApp\Project13\Git\Run-Infrastructure.cmd
```

The sequence is:

```powershell
Set-Location D:\CodexApp\Project13\Git
.\infra\windows\00-Enable-Wsl2.ps1
.\infra\windows\01-Install-Ubuntu2404.ps1
.\infra\windows\03-Configure-WSL.ps1
.\infra\windows\02-Install-DockerDesktop.ps1
.\infra\windows\04-Verify-Infrastructure.ps1
```

`01-Install-Ubuntu2404.ps1` installs the signed Microsoft WSL `2.7.14` MSI
when a modern runtime is absent. It no longer installs the obsolete 5.10.16
kernel package over a modern runtime.

`03-Configure-WSL.ps1` writes `.wslconfig` but deliberately avoids
`wsl --shutdown` and `wsl --terminate` because those calls can put
`LxssManager` into `STOP_PENDING` on this Windows 10 host.

The Ubuntu bootstrap can also be rerun safely from PowerShell:

```powershell
wsl.exe -d Ubuntu-24.04 -u root -- bash /mnt/d/CodexApp/Project13/Git/infra/wsl/bootstrap-ubuntu.sh
```

The bootstrap uses the Aliyun HTTP mirror only to install `ca-certificates`,
then switches to HTTPS and installs the complete base toolchain.

## User access

The Linux user `mars` already exists and its password is set. Administrative
automation should continue to use `wsl.exe -d Ubuntu-24.04 -u root`; do not
store the password in scripts or documentation.

## Verification

```powershell
& 'C:\Program Files\WSL\wsl.exe' --version
& 'C:\Program Files\WSL\wsl.exe' -l -v
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -- uname -a
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -- docker version
```

The expected WSL runtime is `2.7.14`, kernel is `6.18.33.2`, the distro state
is `Running`, and the version is `2`.
