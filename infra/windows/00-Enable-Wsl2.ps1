#Requires -RunAsAdministrator

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $logDir "wsl-enable-$stamp.log"
$rebootFlag = Join-Path $logDir "wsl-reboot-required.flag"

Start-Transcript -Path $logPath -Append
try {
    Write-Host "Enabling WSL2 Windows features. Log: $logPath"

    $features = @(
        "Microsoft-Windows-Subsystem-Linux",
        "VirtualMachinePlatform"
    )

    $rebootRequired = $false
    foreach ($feature in $features) {
        $state = (Get-WindowsOptionalFeature -Online -FeatureName $feature).State
        Write-Host "$feature current state: $state"

        if ($state -ne "Enabled") {
            & dism.exe /online /enable-feature /featurename:$feature /all /norestart
            $dismExit = $LASTEXITCODE
            Write-Host "$feature dism exit code: $dismExit"

            if ($dismExit -eq 3010) {
                $rebootRequired = $true
            }
            elseif ($dismExit -ne 0) {
                throw "Failed to enable $feature. DISM exit code: $dismExit"
            }
        }
    }

    $pendingCbs = Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"
    $pendingRename = $null -ne (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" -Name PendingFileRenameOperations -ErrorAction SilentlyContinue)

    if ($rebootRequired -or $pendingCbs -or $pendingRename) {
        @(
            "WSL2 feature enablement completed.",
            "Reboot Windows before running 01-Install-Ubuntu2404.ps1.",
            "Created: $(Get-Date -Format o)"
        ) | Set-Content -Encoding UTF8 -Path $rebootFlag
        Write-Host "REBOOT REQUIRED. Marker: $rebootFlag"
    }
    else {
        Remove-Item -Force -ErrorAction SilentlyContinue $rebootFlag
        Write-Host "No reboot marker was required. Continue with 01-Install-Ubuntu2404.ps1."
    }
}
finally {
    Stop-Transcript
}

