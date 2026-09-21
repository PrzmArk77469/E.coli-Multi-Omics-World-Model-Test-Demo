[CmdletBinding()]
param(
    [string]$DistroName = "Ubuntu-24.04"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $logDir "verify-$stamp.log"
$statusPath = Join-Path $logDir "last-verification.json"

Start-Transcript -Path $logPath -Append
try {
    & wsl.exe --version
    if ($LASTEXITCODE -ne 0) {
        throw "WSL version check failed."
    }

    & wsl.exe --list --verbose
    if ($LASTEXITCODE -ne 0) {
        throw "WSL distribution listing failed."
    }

    $uname = (& wsl.exe -d $DistroName -- uname -a | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to start $DistroName."
    }

    $gitVersion = (& wsl.exe -d $DistroName -- git --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Git is unavailable inside $DistroName."
    }

    $uvVersion = (& wsl.exe -d $DistroName -- uv --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "uv is unavailable inside $DistroName."
    }

    $dockerVersion = (& wsl.exe -d $DistroName -- docker version --format "{{.Server.Version}}" | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop integration is not available inside $DistroName."
    }

    $status = [ordered]@{
        verified_at = (Get-Date -Format o)
        distro = $DistroName
        uname = $uname
        git = $gitVersion
        uv = $uvVersion
        docker_server = $dockerVersion
        log = $logPath
    }
    $status | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path $statusPath
    Write-Host "Infrastructure verification succeeded."
}
finally {
    Stop-Transcript
}

