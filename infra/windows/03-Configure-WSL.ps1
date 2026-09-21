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
$logPath = Join-Path $logDir "wsl-configure-$stamp.log"
$configPath = Join-Path $env:USERPROFILE ".wslconfig"

Start-Transcript -Path $logPath -Append
try {
    @"
[wsl2]
memory=9GB
processors=8
swap=12GB
localhostForwarding=true

[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
"@ | Set-Content -Encoding ASCII -Path $configPath

    Write-Host "Wrote $configPath"
    # On the inbox Windows 10 WSL build, --shutdown can leave LxssManager in
    # STOP_PENDING. Terminating the distro applies the runtime limits for this
    # run; the remaining VM settings apply on the next normal Windows restart.
    & wsl.exe --terminate $DistroName
    & wsl.exe -d $DistroName -- uname -a
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to start $DistroName."
    }
}
finally {
    Stop-Transcript
}
