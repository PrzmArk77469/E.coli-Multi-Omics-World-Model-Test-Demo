#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$DistroName = "Ubuntu-24.04",
    [string]$InstallRoot = "D:\WSL\Ubuntu-24.04",
    [string]$DownloadRoot = "D:\WSL\Downloads",
    [string]$LinuxUser = "mars",
    [string]$RootfsUrl = "https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/ubuntu-base-24.04.5-base-amd64.tar.gz",
    [string]$RootfsSha256 = "e77b6f10c2590cef872b33ee9f635a0e3fd1f57fb074c0e52b5c7f56147a0c86",
    [string]$WslMsiUrl = "https://github.com/microsoft/WSL/releases/download/2.7.14/wsl.2.7.14.0.x64.msi",
    [string]$WslMsiSha256 = "db084e536279a59e90a26ec598d8aa8a4dff8309f41d078fd06242953ac1ebcd"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$driveLetter = $repoRoot.Substring(0, 1).ToLowerInvariant()
$repoRelativePath = $repoRoot.Substring(2).Replace("\", "/")
$repoWslPath = "/mnt/${driveLetter}${repoRelativePath}"
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $DownloadRoot | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $logDir "ubuntu-install-$stamp.log"
$rebootFlag = Join-Path $logDir "wsl-reboot-required.flag"
$wslMsiPath = Join-Path $DownloadRoot "wsl.2.7.14.0.x64.msi"
$rootfsPath = Join-Path $DownloadRoot "ubuntu-base-24.04.5-base-amd64.tar.gz"
$bootstrapPath = "${repoWslPath}/infra/wsl/bootstrap-ubuntu.sh"

Start-Transcript -Path $logPath -Append
try {
    foreach ($feature in @("Microsoft-Windows-Subsystem-Linux", "VirtualMachinePlatform")) {
        $state = (Get-WindowsOptionalFeature -Online -FeatureName $feature).State
        if ($state -ne "Enabled") {
            throw "$feature is not enabled. Reboot after running 00-Enable-Wsl2.ps1, then retry."
        }
    }

    $modernWsl = $false
    $wslVersionOutput = (& wsl.exe --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $wslVersionOutput -match "WSL") {
        $modernWsl = $true
        Write-Host "Modern WSL runtime is already installed."
    }

    if (-not $modernWsl) {
        if (-not (Test-Path $wslMsiPath)) {
            Write-Host "Downloading Microsoft WSL 2.7.14 to $wslMsiPath."
            Invoke-WebRequest -Uri $WslMsiUrl -OutFile $wslMsiPath -UseBasicParsing
        }

        $actualWslHash = (Get-FileHash -Algorithm SHA256 -Path $wslMsiPath).Hash.ToLowerInvariant()
        if ($actualWslHash -ne $WslMsiSha256.ToLowerInvariant()) {
            throw "WSL MSI SHA256 mismatch. Expected $WslMsiSha256 but found $actualWslHash."
        }

        $signature = Get-AuthenticodeSignature -LiteralPath $wslMsiPath
        if ($signature.Status -ne "Valid") {
            throw "WSL MSI signature validation failed: $($signature.StatusMessage)"
        }

        Write-Host "Installing Microsoft WSL 2.7.14."
        $wslInstaller = Start-Process msiexec.exe -ArgumentList @("/i", $wslMsiPath, "/quiet", "/norestart") -Wait -PassThru
        if ($wslInstaller.ExitCode -notin @(0, 1638, 3010)) {
            throw "WSL runtime installation failed with exit code $($wslInstaller.ExitCode)."
        }
    }

    $registered = (& wsl.exe --list --quiet 2>$null) -split "`r?`n" | Where-Object { $_.Trim() -eq $DistroName }
    if (-not $registered) {
        if (-not (Test-Path $rootfsPath)) {
            Write-Host "Downloading Ubuntu 24.04 rootfs to $rootfsPath."
            Invoke-WebRequest -Uri $RootfsUrl -OutFile $rootfsPath -UseBasicParsing
        }

        $actualRootfsHash = (Get-FileHash -Algorithm SHA256 -Path $rootfsPath).Hash.ToLowerInvariant()
        if ($actualRootfsHash -ne $RootfsSha256.ToLowerInvariant()) {
            throw "Ubuntu rootfs SHA256 mismatch. Expected $RootfsSha256 but found $actualRootfsHash."
        }

        Write-Host "Setting WSL default version to 2."
        & wsl.exe --set-default-version 2
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to set WSL default version."
        }

        Write-Host "Importing $DistroName into $InstallRoot."
        & wsl.exe --import $DistroName $InstallRoot $rootfsPath --version 2
        if ($LASTEXITCODE -ne 0) {
            throw "Ubuntu import failed with exit code $LASTEXITCODE."
        }
    }

    Write-Host "Configuring Linux user and base packages."
    $linuxCommand = @"
set -euo pipefail
if ! id -u $LinuxUser >/dev/null 2>&1; then
  useradd -m -s /bin/bash -G sudo $LinuxUser
fi
cat >/etc/wsl.conf <<'EOF'
[user]
default=$LinuxUser

[boot]
systemd=true

[interop]
appendWindowsPath=true
EOF
"@
    & wsl.exe -d $DistroName -u root -- bash -lc $linuxCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Linux user configuration failed."
    }

    & wsl.exe -d $DistroName -u root -- bash $bootstrapPath
    if ($LASTEXITCODE -ne 0) {
        throw "Ubuntu bootstrap failed. Review the timestamped log."
    }

    Remove-Item -Force -ErrorAction SilentlyContinue $rebootFlag
    Write-Host "Ubuntu $DistroName is ready. Run passwd mars before using sudo."
}
finally {
    Stop-Transcript
}
