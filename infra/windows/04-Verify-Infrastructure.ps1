[CmdletBinding()]
param(
    [string]$DistroName = "Ubuntu-24.04",
    [string]$LinuxUser = "mars",
    [string]$WslExe = "C:\Program Files\WSL\wsl.exe",
    [int]$ProxyPort = 7897,
    [string]$FirewallRuleName = "Project13 Clash Verge WSL 7897"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $logDir "verify-$stamp.log"
$statusPath = Join-Path $logDir "last-verification.json"

if (-not (Test-Path -LiteralPath $WslExe)) {
    $resolvedWsl = Get-Command wsl.exe -ErrorAction Stop
    $WslExe = $resolvedWsl.Source
}

$driveLetter = $repoRoot.Substring(0, 1).ToLowerInvariant()
$repoRelativePath = $repoRoot.Substring(2).Replace("\", "/")
$repoWslPath = "/mnt/${driveLetter}${repoRelativePath}"

function Invoke-WslCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = (& $WslExe @Arguments 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "WSL command failed: $($Arguments -join ' ')`n$output"
    }
    return $output
}

function Convert-WslText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    return ($Text -replace "`0", "").Trim()
}

Start-Transcript -Path $logPath -Append
try {
    $wslVersionText = Convert-WslText -Text (Invoke-WslCommand -Arguments @("--version"))
    $wslVersion = if ($wslVersionText -match "2\.7\.14\.0") { "2.7.14" } else { $wslVersionText }
    $distroListText = Convert-WslText -Text (Invoke-WslCommand -Arguments @("--list", "--verbose"))
    $distroList = @(
        $distroListText -split "\r?\n" |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    ) -join "; "
    $uname = Invoke-WslCommand -Arguments @("-d", $DistroName, "--", "uname", "-a")
    $gitVersion = Invoke-WslCommand -Arguments @("-d", $DistroName, "--", "git", "--version")
    $uvVersion = Invoke-WslCommand -Arguments @("-d", $DistroName, "--", "uv", "--version")
    $dockerClient = Invoke-WslCommand -Arguments @(
        "-d", $DistroName, "--", "docker", "version", "--format", "{{.Client.Version}}"
    )

    $dockerServer = $null
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        $output = (& $WslExe -d $DistroName -- docker version --format "{{.Server.Version}}" 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $output) {
            $dockerServer = $output
            break
        }
        Write-Host "Waiting for Docker Desktop integration, attempt $attempt/12."
        Start-Sleep -Seconds 10
    }
    if (-not $dockerServer) {
        throw "Docker Desktop integration is not available inside $DistroName."
    }

    $dockerHelloWorld = Invoke-WslCommand -Arguments @(
        "-d", $DistroName, "--", "docker", "run", "--rm", "hello-world"
    )
    if ($dockerHelloWorld -notmatch "Hello from Docker") {
        throw "Docker hello-world did not produce the expected output."
    }

    $clashReachable = Test-NetConnection -ComputerName "127.0.0.1" -Port $ProxyPort -InformationLevel Quiet
    if (-not $clashReachable) {
        throw "Clash Verge is not listening on 127.0.0.1:$ProxyPort."
    }

    $wslHost = Invoke-WslCommand -Arguments @(
        "-d", $DistroName, "-u", $LinuxUser, "--", "bash", "-lc", "printenv WSL_HOST"
    )
    if (-not $wslHost) {
        throw "WSL_HOST is not configured for $LinuxUser."
    }

    $githubHttp = Invoke-WslCommand -Arguments @(
        "-d", $DistroName, "-u", $LinuxUser, "--", "bash", "-lc",
        "curl -sS -o /dev/null -w '%{http_code}' --max-time 30 https://github.com"
    )
    if ($githubHttp -ne "200") {
        throw "GitHub proxy verification returned HTTP $githubHttp."
    }

    $aliyunHttp = Invoke-WslCommand -Arguments @(
        "-d", $DistroName, "-u", $LinuxUser, "--", "bash", "-lc",
        "curl -sS -o /dev/null -w '%{http_code}' --max-time 30 https://mirrors.aliyun.com"
    )
    if ($aliyunHttp -notin @("200", "301", "302")) {
        throw "Aliyun direct verification returned HTTP $aliyunHttp."
    }

    $gitRemote = Invoke-WslCommand -Arguments @(
        "-d", $DistroName, "-u", $LinuxUser, "--", "git", "-C", $repoWslPath,
        "ls-remote", "--heads", "origin"
    )
    if (-not $gitRemote) {
        throw "The Git origin remote did not return any heads."
    }

    $firewallRule = Get-NetFirewallRule -DisplayName $FirewallRuleName -ErrorAction Stop
    if (-not $firewallRule.Enabled -or $firewallRule.Action -ne "Allow") {
        throw "Firewall rule '$FirewallRuleName' is not enabled or is not an allow rule."
    }

    $status = [ordered]@{
        verified_at = (Get-Date -Format o)
        distro = $DistroName
        linux_user = $LinuxUser
        wsl_version = $wslVersion
        distro_list = $distroList
        uname = $uname
        git = $gitVersion
        uv = $uvVersion
        docker_client = $dockerClient
        docker_server = $dockerServer
        docker_hello_world = "ok"
        clash_proxy_port = $ProxyPort
        clash_reachable = $clashReachable
        wsl_host = $wslHost
        github_http = [int]$githubHttp
        aliyun_http = [int]$aliyunHttp
        git_remote = "ok"
        firewall_rule = $FirewallRuleName
        log = $logPath
    }
    $status | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path $statusPath
    Write-Host "Infrastructure verification succeeded."
}
finally {
    Stop-Transcript
}
