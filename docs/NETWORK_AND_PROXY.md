# Network and Proxy

## Working topology

Clash Verge runs on Windows and exposes a mixed HTTP proxy on
`127.0.0.1:7897`. System proxy and TUN mode are not required for this project.

```text
Windows applications
  -> http://127.0.0.1:7897

Docker Desktop engine
  -> http://127.0.0.1:7897

WSL Ubuntu
  -> http://<windows-host-gateway>:7897
```

The WSL gateway is obtained dynamically from `/proc/net/route`. On the current
host it has been observed as `172.23.144.1`, but the address must not be
hard-coded.

## Clash Verge settings

Required settings:

- Mode: `Rule`
- Mixed port: `7897`
- Allow LAN: enabled
- System proxy: not required
- TUN mode: disabled
- Policy groups used by project rules: `Ghelper` and `AI专用`

The listener must accept connections from the WSL subnet. Windows Firewall is
restricted to the private address range `172.16.0.0/12`.

## Clash rules

Add project-specific rules to the active profile's `rules` `prepend` list,
before the subscription's own rules. Put explicit domestic services in
`DIRECT` and external development services in the existing `Ghelper` group.
Do not place `GEOIP,CN,DIRECT` or `MATCH` inside `prepend`; those catch-all
rules must remain at the end of the generated rule list.

Representative project rules:

```yaml
prepend:
  - 'DOMAIN-SUFFIX,docker.io,Ghelper'
  - 'DOMAIN-SUFFIX,docker.com,Ghelper'
  - 'DOMAIN-SUFFIX,dockerusercontent.com,Ghelper'
  - 'DOMAIN-SUFFIX,github.com,Ghelper'
  - 'DOMAIN-SUFFIX,githubusercontent.com,Ghelper'
  - 'DOMAIN-SUFFIX,githubassets.com,Ghelper'
  - 'DOMAIN-SUFFIX,ghcr.io,Ghelper'
  - 'DOMAIN-SUFFIX,quay.io,Ghelper'
  - 'DOMAIN-SUFFIX,gcr.io,Ghelper'
  - 'DOMAIN-SUFFIX,k8s.io,Ghelper'
  - 'DOMAIN-SUFFIX,mcr.microsoft.com,Ghelper'
  - 'DOMAIN-SUFFIX,nvidia.com,Ghelper'
  - 'DOMAIN-SUFFIX,nvcr.io,Ghelper'
  - 'DOMAIN-SUFFIX,huggingface.co,Ghelper'
  - 'DOMAIN-SUFFIX,hf.co,Ghelper'
  - 'DOMAIN-SUFFIX,pypi.org,Ghelper'
  - 'DOMAIN-SUFFIX,pythonhosted.org,Ghelper'
  - 'DOMAIN-SUFFIX,nodejs.org,Ghelper'
  - 'DOMAIN-SUFFIX,nodesource.com,Ghelper'
  - 'DOMAIN-SUFFIX,npmjs.org,Ghelper'
  - 'DOMAIN-SUFFIX,npmjs.com,Ghelper'
  - 'DOMAIN-SUFFIX,aliyun.com,DIRECT'
  - 'DOMAIN-SUFFIX,aliyuncs.com,DIRECT'
  - 'DOMAIN-SUFFIX,alibabacloud.com,DIRECT'
  - 'DOMAIN-SUFFIX,registry.npmmirror.com,DIRECT'
append: []
delete: []
```

The generated profile already ends with:

```yaml
- GEOIP,CN,DIRECT
- MATCH, Ghelper
```

Do not append duplicate `GEOIP` or `MATCH` entries after that final match.

## Docker Desktop

Docker Desktop stores its manual proxy settings in
`C:\Users\Mars\AppData\Roaming\Docker\settings-store.json`.

Relevant settings:

```json
{
  "IntegratedWslDistros": [
    "Ubuntu-24.04"
  ],
  "EnableIntegrationWithDefaultWslDistro": false,
  "proxyHttpMode": "manual",
  "overrideProxyHttp": "http://127.0.0.1:7897",
  "overrideProxyHttps": "http://127.0.0.1:7897",
  "overrideProxyExclude": "localhost,127.0.0.1,::1"
}
```

If Docker Desktop is restarted and loses the integration, rerun:

```powershell
& 'C:\Users\Mars\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe' `
  -NoProfile -ExecutionPolicy Bypass `
  -File 'D:\CodexApp\Project13\Git\infra\windows\02-Install-DockerDesktop.ps1'
```

## WSL shell proxy

The idempotent installer writes a marked block near the top of
`/home/mars/.bashrc`:

```powershell
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -u mars `
  -- bash /mnt/d/CodexApp/Project13/Git/infra/wsl/configure-proxy.sh
```

The block exports:

```text
WSL_HOST
http_proxy
https_proxy
HTTP_PROXY
HTTPS_PROXY
NO_PROXY
no_proxy
```

`NO_PROXY` keeps localhost, WSL/Docker private networks, and Aliyun domains
direct. A backup of `.bashrc` is created before the first modification.

## Windows Firewall

Rule name:

```text
Project13 Clash Verge WSL 7897
```

Rule scope:

```text
Direction: Inbound
Action: Allow
Protocol: TCP
Local port: 7897
Remote address: 172.16.0.0/12
Program: D:\Program Files\Clash Verge\verge-mihomo.exe
```

This permits only WSL/private-network sources and does not expose port `7897`
to the public internet.

## Validation

The full verification script regenerates `logs/last-verification.json`:

```powershell
& 'C:\Users\Mars\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe' `
  -NoProfile -ExecutionPolicy Bypass `
  -File 'D:\CodexApp\Project13\Git\infra\windows\04-Verify-Infrastructure.ps1'
```

Manual checks:

```powershell
Test-NetConnection 127.0.0.1 -Port 7897
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -- docker run --rm hello-world
& 'C:\Program Files\WSL\wsl.exe' -d Ubuntu-24.04 -u mars -- bash -lc 'curl -I https://github.com'
```

`http://127.0.0.1:7897/` is the proxy listener, not a dashboard. Do not judge
the proxy state by opening that URL in a browser.

Do not add an untrusted Docker registry mirror while this verified proxy path
is working.
