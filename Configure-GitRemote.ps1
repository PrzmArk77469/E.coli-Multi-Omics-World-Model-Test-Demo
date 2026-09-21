[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUrl,

    [string]$RemoteName = "origin",
    [string]$Branch = "main"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
Set-Location $repoRoot

$existing = git remote get-url $RemoteName 2>$null
if ($LASTEXITCODE -eq 0 -and $existing) {
    git remote set-url $RemoteName $RemoteUrl
}
else {
    git remote add $RemoteName $RemoteUrl
}

git push -u $RemoteName $Branch
if ($LASTEXITCODE -ne 0) {
    throw "Failed to push $Branch to $RemoteName."
}
