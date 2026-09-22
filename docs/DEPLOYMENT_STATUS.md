# Deployment Status

Last updated: 2026-09-22

## Completed

- Windows remains Windows 10 Home 22H2 build 19045; no Windows upgrade was
  performed.
- Microsoft WSL runtime `2.7.14` and Linux kernel
  `6.18.33.2-microsoft-standard-WSL2` are installed.
- Ubuntu `24.04` is registered as `Ubuntu-24.04`, runs as WSL2, and stores its
  VHDX under `D:\WSL\Ubuntu-24.04`.
- Ubuntu user `mars` is configured. Git `2.43.0`, Python `3.12.3`, and
  `uv 0.12.17` are available.
- Node.js `v22.23.2` and npm `10.9.8` are installed through nvm `0.40.4`.
  Stable `/usr/local/bin` links make `node`, `npm`, `npx`, and `corepack`
  available to non-login shells and Hermes.
- Docker Desktop `4.91.0` with Linux Engine `29.8.0` is installed at
  `D:\DockerDesktop`; persistent data is under `D:\DockerDesktopData`.
- Docker Desktop WSL integration is enabled for `Ubuntu-24.04`.
- Docker Desktop uses the Clash Verge HTTP proxy at
  `http://127.0.0.1:7897`.
- Ubuntu uses the Windows-host gateway proxy through the idempotent
  `infra/wsl/configure-proxy.sh` setup.
- Clash Verge permits LAN access on mixed port `7897`; system proxy and TUN
  mode remain disabled.
- Windows Firewall allows only `172.16.0.0/12` to reach
  `verge-mihomo.exe:7897`.
- GitHub proxy access, Aliyun direct access, Git remote access, and Docker
  `hello-world` have all been verified from Ubuntu.
- The repository is connected to
  `https://github.com/PrzmArk77469/E.coli-Multi-Omics-World-Model-Test-Demo.git`
  as `origin`.
- A local rollback remote named `backup` points to
  `D:\CodexApp\Project13\GitBackup.git`.
- The latest verification is recorded locally in
  `logs/last-verification.json` and the matching `logs/verify-*.log`.
- Existing omics data contains about 2,134 files and 13.27 GB on disk,
  including MG1655 references, ENA/PRIDE/MetaboLights assets, RegulonDB,
  iML1515, metabolomics, proteomics, and integrated metadata masters.
- A CPU-only 2,000-agent simulation MVP is implemented with five schemas,
  uniform-grid spatial hashing, neighborhood detection, a priority event
  queue, JSONL event logging, and `NO_EFFECT`, `MODIFY`, and `BIND` outcomes.
- The 2,000-agent / 80-step integration test completes in seconds and produces
  all three required outcomes and abstract complexes.
- An observed-only condition-mapping layer assigns stable unified sample IDs and
  condition IDs without modifying `sample_master.tsv.gz`.
- The first full mapping covers 602,778 source rows, 601,616 unified sample IDs,
  and 558 observed condition signatures; evidence, confidence, and conflicts
  remain attached to every field.
- A resumable ENA BioSample XML fetcher is implemented. Three MG1655 samples
  are cached as a contract demonstration; bulk retrieval remains a deliberate
  later operation.
- Synthetic gap filling is isolated in `synthetic_condition_fill.tsv.gz` and
  never overwrites the observed map. The seed-42 Demo selected 2,000
  source-stratified contexts and attached them to all 2,000 agents.
- The condition-aware event run completed with 58,558 events, all three
  required outcomes, and 237 complexes. The event and agent-context logs are
  local reproducibility artifacts, not Git payloads.
- The condition-aware Demo now exports an offline browser replay viewer with a
  Three.js 3D cell envelope, all 2,000 agents, 58,558 event records, complexes,
  timeline controls, provenance filters, and agent inspection. The reusable
  viewer template and vendor assets are versioned; generated data remains a
  local artifact.
- Nous Research Hermes Agent `v0.21.4` is installed under
  `/home/mars/.hermes` from upstream commit `836b5f82`. The CLI, ACP entry
  point, browser/computer-use support, Playwright Chromium, memory, cron,
  skills, terminal, and file tools are available.
- Hermes configuration was migrated to version `v45`. Its reviewed installer
  hash, idempotent WSL installer, and operating procedure are recorded in the
  repository. No API key or OAuth credential is stored in Git.
- Hermes is configured with provider `deepseek`, model `deepseek-flash`, and
  base URL `https://api.deepseek.com/v1`. The credential remains only in
  `/home/mars/.hermes/.env`.
- Hermes passed a real inference smoke test with output `HERMES_OK` and a real
  terminal-tool test that returned the repository's `main` branch status.
- Hermes terminal commands now default to
  `/mnt/d/CodexApp/Project13/Git`, so repository-scoped work starts in the
  correct directory.
- `docs/SYSTEM_ARCHITECTURE.md` is the canonical system map for onboarding,
  deployment review, provenance review, and rollback planning.

## Current boundary

The local execution, container, Git, network, condition-aware simulation, and
observed/synthetic separation foundations are operational. The official
Nous Research Hermes Agent is installed, authenticated to DeepSeek Flash, and
verified through inference and terminal tools. Alibaba Cloud resources and bulk
ENA BioSample retrieval have not yet been provisioned.

## Immediate next work

1. Use Hermes for repository-scoped planning, implementation, and verification
   tasks against the current commit.
2. Deploy the Alibaba Cloud CPU control plane and private OSS before adding an
   on-demand GPU worker.
3. Replace synthetic Demo fields with real BioSample attributes in the next ENA
   retrieval batch.

## Required user decisions

- Decide whether to mirror GitHub to Alibaba Cloud Codeup for mainland ECS
  access.
- Decide when to provision the first CPU ECS and private OSS bucket.
- Decide which optional external-tool credentials, if any, should be added
  beyond the current DeepSeek inference configuration.
