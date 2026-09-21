# E. coli Multi-Omics World Model

This repository contains source code, configuration, documentation, tests, and
small reproducibility metadata for the E. coli MG1655 multi-omics world-model
Demo.

Raw data, reference snapshots, generated artifacts, credentials, and runtime
logs are intentionally excluded from Git. The canonical large-data location is
the project data tree outside this repository or an object-storage bucket.

## Repository boundaries

- Tracked here: source code, schemas, small fixtures, configuration templates,
  infrastructure automation, operations documentation, and data manifests that
  do not contain restricted payloads.
- Not tracked here: FASTQ, PRIDE files, MetaboLights payloads, model
  checkpoints, OSS mirrors, private keys, API tokens, and generated logs.
- Local project data: `D:\CodexApp\Project13\EcoliOmics`
- Local Git repository: `D:\CodexApp\Project13\Git`
- Local deployment logs: `D:\CodexApp\Project13\Git\logs`

## Infrastructure sequence

1. Run the elevated Windows script to enable WSL2.
2. Reboot if the script requests it.
3. Run the Ubuntu 24.04 import script. The distro VHDX is placed on D:.
4. Run the Ubuntu bootstrap script as root.
5. Install and configure Docker Desktop with its data root on D:.
6. Verify Docker integration from Ubuntu.
7. Use the configured Git remote and push the repository.
8. Deploy the Alibaba Cloud CPU control plane before enabling GPU workers.

See `docs/INFRASTRUCTURE.md` for the complete topology and
`docs/LOGGING_AND_ROLLBACK.md` for recovery instructions. Current progress is
recorded in `docs/DEPLOYMENT_STATUS.md`. New Codex conversations should begin
with `docs/NEW_CONVERSATION_CONTEXT.md`.

## Git workflow

```powershell
Set-Location D:\CodexApp\Project13\Git
git status
git add .
git commit -m "Bootstrap project infrastructure"
git push -u origin main
```

The configured `origin` is
`https://github.com/PrzmArk77469/Git.git`. A local rollback remote named
`backup` points to `D:\CodexApp\Project13\GitBackup.git`.
