#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$DistroName = "Ubuntu-24.04"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $logDir "resume-$stamp.log"

Start-Transcript -Path $logPath -Append
try {
    & (Join-Path $repoRoot "infra\windows\01-Install-Ubuntu2404.ps1") -DistroName $DistroName
    if (-not $?) {
        throw "Ubuntu installation script failed."
    }

    & (Join-Path $repoRoot "infra\windows\03-Configure-WSL.ps1") -DistroName $DistroName
    if (-not $?) {
        throw "WSL configuration script failed."
    }

    & (Join-Path $repoRoot "infra\windows\02-Install-DockerDesktop.ps1") -DistroName $DistroName
    if (-not $?) {
        throw "Docker Desktop configuration script failed."
    }

    & (Join-Path $repoRoot "infra\windows\04-Verify-Infrastructure.ps1") -DistroName $DistroName
    if (-not $?) {
        throw "Infrastructure verification failed."
    }

    Write-Host "Infrastructure resume completed successfully."
}
finally {
    Stop-Transcript
}
