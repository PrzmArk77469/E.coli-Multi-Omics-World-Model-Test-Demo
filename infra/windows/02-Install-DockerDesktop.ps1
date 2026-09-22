#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$InstallRoot = "D:\DockerDesktop",
    [string]$DataRoot = "D:\DockerDesktopData",
    [string]$DistroName = "Ubuntu-24.04",
    [string]$ProxyUrl = "http://127.0.0.1:7897",
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

    $dockerCliPath = Join-Path $InstallRoot "resources\bin\docker.exe"
    if ($dockerCliPath -and (Test-Path $dockerCliPath)) {
        & $dockerCliPath desktop stop 2>$null | Out-Null
    }

    $settingsDir = Join-Path $env:APPDATA "Docker"
    $settingsPath = Join-Path $settingsDir "settings-store.json"
    New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null

    if (Test-Path $settingsPath) {
        $settings = Get-Content -Raw -LiteralPath $settingsPath | ConvertFrom-Json
    }
    else {
        $settings = [pscustomobject]@{}
    }

    $settings | Add-Member -NotePropertyName "CustomWslDistroDir" -NotePropertyValue $DataRoot -Force
    $settings | Add-Member -NotePropertyName "IntegratedWslDistros" -NotePropertyValue @($DistroName) -Force
    $settings | Add-Member -NotePropertyName "EnableIntegrationWithDefaultWslDistro" -NotePropertyValue $false -Force

    $proxyEndPoint = $null
    if ($ProxyUrl -match "127\.0\.0\.1:(\d+)") {
        $proxyEndPoint = [int]$Matches[1]
    }
    if ($proxyEndPoint -and (Test-NetConnection -ComputerName "127.0.0.1" -Port $proxyEndPoint -InformationLevel Quiet)) {
        Write-Host "Configuring Docker Desktop proxy: $ProxyUrl"
        $settings | Add-Member -NotePropertyName "proxyHttpMode" -NotePropertyValue "manual" -Force
        $settings | Add-Member -NotePropertyName "overrideProxyHttp" -NotePropertyValue $ProxyUrl -Force
        $settings | Add-Member -NotePropertyName "overrideProxyHttps" -NotePropertyValue $ProxyUrl -Force
        $settings | Add-Member -NotePropertyName "overrideProxyExclude" -NotePropertyValue "localhost,127.0.0.1,::1" -Force
    }
    else {
        Write-Warning "No local proxy is listening at $ProxyUrl. Docker Hub access may require Clash Verge or a Docker registry mirror."
    }

    [IO.File]::WriteAllText(
        $settingsPath,
        ($settings | ConvertTo-Json -Depth 20),
        [Text.UTF8Encoding]::new($false)
    )

    if (-not $installedDocker) {
        throw "Docker Desktop executable was not found after installation."
    }

    Write-Host "Starting Docker Desktop with $DistroName WSL integration."
    Start-Process $installedDocker | Out-Null

    $dockerVersion = $null
    for ($attempt = 1; $attempt -le 18; $attempt++) {
        $dockerVersion = (& $dockerCliPath version --format "{{.Server.Version}}" 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $dockerVersion) {
            break
        }
        Write-Host "Waiting for Docker Engine, attempt $attempt/18."
        Start-Sleep -Seconds 10
    }
    if (-not $dockerVersion) {
        throw "Docker Desktop did not start its Linux engine."
    }

    $ubuntuDockerVersion = $null
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        $ubuntuDockerVersion = (& wsl.exe -d $DistroName -- docker version --format "{{.Server.Version}}" 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $ubuntuDockerVersion) {
            break
        }
        Write-Host "Waiting for Docker Desktop integration in $DistroName, attempt $attempt/12."
        Start-Sleep -Seconds 5
    }
    if (-not $ubuntuDockerVersion) {
        throw "Docker Desktop integration is not available inside $DistroName."
    }

    Write-Host "Docker Desktop $dockerVersion and $DistroName integration are ready."
}
finally {
    Stop-Transcript
}
