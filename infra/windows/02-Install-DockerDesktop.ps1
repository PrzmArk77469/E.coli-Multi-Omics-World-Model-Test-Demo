#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$InstallRoot = "D:\DockerDesktop",
    [string]$DataRoot = "D:\DockerDesktopData",
    [string]$DistroName = "Ubuntu-24.04",
    [string]$InstallerUrl = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$logDir = Join-Path $repoRoot "logs"
$downloadRoot = "D:\DockerDesktopDownloads"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $logDir "docker-desktop-$stamp.log"
$installerPath = Join-Path $downloadRoot "DockerDesktopInstaller.exe"

Start-Transcript -Path $logPath -Append
try {
    $installedDocker = @(
        (Join-Path $InstallRoot "Docker Desktop.exe"),
        "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $installedDocker) {
        if (-not (Test-Path $installerPath)) {
            Write-Host "Downloading Docker Desktop installer."
            Invoke-WebRequest -Uri $InstallerUrl -OutFile $installerPath -UseBasicParsing
        }

        Write-Host "Installing Docker Desktop. Large data root: $DataRoot"
        $installerArgs = @(
            "install",
            "--user",
            "--quiet",
            "--accept-license",
            "--backend=wsl-2",
            "--installation-dir=$InstallRoot",
            "--wsl-default-data-root=$DataRoot"
        )
        $installer = Start-Process $installerPath -ArgumentList $installerArgs -Wait -PassThru
        if ($installer.ExitCode -notin @(0, 3010)) {
            throw "Docker Desktop installation failed with exit code $($installer.ExitCode)."
        }

        $installedDocker = @(
            (Join-Path $InstallRoot "Docker Desktop.exe"),
            "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    else {
        Write-Host "Docker Desktop is already installed."
    }

    Write-Host "Starting Docker Desktop and configuring the Ubuntu integration."
    if ($installedDocker) {
        Start-Process $installedDocker | Out-Null
        Start-Sleep -Seconds 20
    }

    $dockerCli = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($dockerCli) {
        & $dockerCli.Source desktop enable integration --distro $DistroName
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Docker Desktop CLI integration command was not accepted. Enable $DistroName manually in Settings > Resources > WSL integration."
        }
    }
    else {
        Write-Warning "Docker CLI is not on PATH yet. Sign out or restart Docker Desktop, then enable $DistroName in WSL integration settings."
    }

    $settingsDir = Join-Path $env:APPDATA "Docker"
    New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null
    Write-Host "Docker settings directory: $settingsDir"
    Write-Host "Verify CustomWslDistroDir is $DataRoot in Docker Desktop settings."
}
finally {
    Stop-Transcript
}
