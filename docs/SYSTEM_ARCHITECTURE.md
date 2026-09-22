# System Architecture

Last updated: 2026-09-22

## 1. Purpose

This repository is an engineering test Demo for an E. coli MG1655 multi-omics
world-model workflow. It validates the complete path from observed metadata,
through condition mapping and agent simulation, to event logging and
interactive replay.

The current implementation is intentionally a workflow proof. Synthetic
agents, rules, positions, and missing condition values are not calibrated
biological predictions.

## 2. System overview

Solid nodes are implemented and locally verified. Dashed nodes are planned
extensions and must not be treated as deployed infrastructure. Hermes is
installed locally, but model authentication is still pending.

```mermaid
flowchart TB
    User["Researcher / Demo audience"]
    Codex["Codex workflow and new-conversation context"]
    GitHub["GitHub repository<br/>source and documentation"]
    Local["Windows + WSL2 Ubuntu 24.04<br/>D: workspace"]
    Docker["Docker Desktop<br/>Linux engine"]
    Data["EcoliOmics data tree<br/>raw, reference, processed, integrated"]
    Observed["Observed sample master"]
    Mapping["Condition mapping"]
    Sidecar["Synthetic condition sidecar"]
    Context["Unified sample + condition contexts"]
    Engine["2,000-agent event engine"]
    Events["Events, complexes, summary, manifest"]
    Viewer["Interactive 3D replay viewer"]
    Hermes["Nous Research Hermes Agent<br/>installed; model auth pending"]
    ECS["Alibaba Cloud CPU ECS<br/>planned"]
    OSS["Private OSS bucket<br/>planned"]
    GPU["On-demand GPU ECS<br/>planned"]

    User --> Viewer
    User --> GitHub
    Codex --> Local
    GitHub <--> Local
    Local --> Docker
    Data --> Observed
    Observed --> Mapping
    Mapping --> Context
    Mapping --> Sidecar
    Sidecar --> Context
    Context --> Engine
    Engine --> Events
    Events --> Viewer
    Local --> Hermes
    Hermes --> Engine
    Local -. SSH .-> ECS
    ECS -.-> OSS
    ECS -.-> GPU

    classDef done fill:#dff5ef,stroke:#237a68,color:#102d28,stroke-width:1.5px;
    classDef data fill:#fff2cc,stroke:#9a6b00,color:#3d2a00,stroke-width:1.5px;
    classDef planned fill:#f2f2f2,stroke:#777,color:#333,stroke-dasharray:5 4;
    class User,Codex,GitHub,Local,Docker,Hermes,Engine,Viewer done;
    class Data,Observed,Mapping,Sidecar,Context,Events data;
    class ECS,OSS,GPU planned;
```

## 3. End-to-end execution

```mermaid
flowchart LR
    A["Read sample_master.tsv.gz"]
    B["Normalize observed fields"]
    C["Assign unified_sample_id<br/>and condition_id"]
    D["Generate labeled synthetic sidecar"]
    E["Select 2,000 contexts"]
    F["Attach context to every agent"]
    G["Spatial hash + neighbor discovery"]
    H["Priority event queue + rule matching"]
    I["NO_EFFECT / MODIFY / BIND"]
    J["Write events + summary + manifest"]
    K["Export replay payload and HTML"]

    A --> B --> C --> D --> E --> F
    F --> G --> H --> I --> J --> K
```

The verified seed-42 run produces:

| Metric | Value |
|---|---:|
| Source rows | 602,778 |
| Demo contexts | 2,000 |
| Conditioned agents | 2,000 |
| Unique effective conditions | 415 |
| Events | 58,558 |
| `NO_EFFECT` | 57,928 |
| `MODIFY` | 393 |
| `BIND` | 237 |
| Complexes | 237 |

## 4. Data and provenance boundary

Observed and synthetic data are separate authorities. A generated value never
overwrites an observed field.

```mermaid
flowchart TB
    Raw["Public multi-omics source metadata"]
    Master["sample_master.tsv.gz"]
    Registry["Observed condition registry"]
    Fill["synthetic_condition_fill.tsv.gz"]
    Effective["Effective Demo context join"]
    Agent["Agent context attached by agent_uid"]
    Log["Event and provenance logs"]

    Raw --> Master --> Registry
    Registry --> Effective
    Fill --> Effective
    Effective --> Agent --> Log

    Registry -. observed fields remain authoritative .-> Effective
    Fill -. fields are labeled SYNTHETIC or MIXED .-> Effective
```

Important identifiers:

- `unified_sample_id` identifies one source record.
- `condition_id` identifies one normalized medium/genotype/treatment/timepoint
  signature and excludes replicate.
- `data_origin` distinguishes `OBSERVED`, `MIXED`, and `SYNTHETIC`.

## 5. Runtime and deployment topology

```mermaid
flowchart TB
    Windows["Windows 10 host<br/>no Windows upgrade"]
    WSL["Ubuntu-24.04 WSL2<br/>VHDX on D:"]
    Docker["Docker Desktop<br/>data on D:"]
    Proxy["Clash Verge mixed port 7897<br/>LAN access enabled"]
    Repo["Git workspace<br/>origin + local backup"]
    Hermes["Hermes Agent<br/>local CLI and tools"]
    CPU["Alibaba Cloud CPU ECS<br/>planned control plane"]
    OSS["Private OSS<br/>planned data and checkpoints"]
    GPU["GPU ECS worker<br/>planned, on demand"]

    Windows --> WSL
    Windows --> Docker
    WSL --> Hermes
    WSL <--> Proxy
    Docker <--> Proxy
    WSL <--> Repo
    Proxy <--> Repo
    WSL -. SSH .-> CPU
    CPU <--> OSS
    CPU -. start / stop .-> GPU

    classDef local fill:#dff5ef,stroke:#237a68,color:#102d28;
    classDef planned fill:#f2f2f2,stroke:#777,color:#333,stroke-dasharray:5 4;
    class Windows,WSL,Docker,Proxy,Repo,Hermes local;
    class CPU,OSS,GPU planned;
```

The local repository path stays `D:\CodexApp\Project13\Git` because the
infrastructure scripts and logs reference it. Renaming the GitHub repository
does not require renaming this stable local directory.

## 6. Component responsibilities

| Component | Responsibility | Current state |
|---|---|---|
| `src/ecoli_world/conditions.py` | Normalize observed fields and build stable IDs | Implemented |
| `src/ecoli_world/synthetic_conditions.py` | Generate isolated, deterministic gap-filling sidecar | Implemented |
| `src/ecoli_world/engine.py` | Run agents through the event engine | Implemented |
| `src/ecoli_world/spatial.py` | Uniform spatial hash and neighborhood discovery | Implemented |
| `src/ecoli_world/events.py` | Priority event queue | Implemented |
| `schemas/` | Five versioned entity contracts | Implemented |
| `src/ecoli_world/visualization.py` | Export compact replay data and local viewer | Implemented |
| `visualizations/demo_engine.html` | Interactive Three.js replay interface | Implemented |
| `infra/windows/` | WSL, Ubuntu, Docker installation and verification | Implemented locally |
| `infra/wsl/` | Ubuntu bootstrap and proxy configuration | Implemented locally |
| Nous Research Hermes Agent | Agent-assisted planning and orchestration | Installed; model authentication pending |
| Alibaba Cloud | CPU control plane, private OSS, on-demand GPU | Planned |

## 7. Repository map

```text
README.md                       Project landing page and quick start
AGENTS.md                       Repository-level agent operating rules
docs/
  README.md                     Documentation index
  SYSTEM_ARCHITECTURE.md        This system map and review guide
  *.md                          Runtime, data, network, and status documents
  project/                      Original designs and feasibility studies
schemas/                        Five simulation entity schemas
src/ecoli_world/                Python simulation and condition-mapping code
tests/                          Unit and end-to-end tests
infra/windows/                  Windows and Docker setup scripts
infra/wsl/                      Ubuntu bootstrap, proxy, and Hermes scripts
metadata/download_queue/        Small reproducibility manifests
visualizations/                 Replay and architecture HTML assets
```

Git tracks source, contracts, automation, small metadata, and documentation.
It does not track:

- `EcoliOmics/raw`, `reference`, `processed`, and `integrated` payloads;
- model checkpoints and generated replay payloads;
- credentials, keys, runtime logs, and temporary files.

## 8. Verification and rollback

The current verified baseline uses Ubuntu 24.04 WSL and passes:

```bash
cd /mnt/d/CodexApp/Project13/Git
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: 16 tests pass, including the 2,000-agent end-to-end condition Demo.

Runtime evidence is stored locally under `logs/` and includes infrastructure
verification plus `condition-demo-42.json` hashes and outcome totals. The local
`backup` remote provides an additional rollback point independent of GitHub.
Hermes `v0.21.4` passes core dependency, tool, and configuration diagnostics.
Its remaining actionable item is model authentication; SQLite and optional
tool warnings are non-blocking.

## 9. Review checklist

1. Confirm that observed metadata enters through `sample_master.tsv.gz`.
2. Confirm that observed and synthetic fields remain separately traceable.
3. Confirm that every agent receives a stable condition context.
4. Confirm that the event engine emits all three required outcomes.
5. Confirm that summary, manifest, event log, and replay payload agree.
6. Treat all current simulation positions and rules as engineering fixtures.
7. Keep the verified simulation baseline intact while Hermes is connected to a
   hosted model provider.
8. Add Alibaba Cloud and bulk ENA retrieval only after preserving this verified
   local baseline.

## 10. Next milestones

1. Rename and maintain the canonical GitHub repository.
2. Authenticate the installed Hermes Agent and run a repository-scoped smoke
   task.
3. Connect Hermes to the remote execution model after local authentication is
   verified.
4. Provision the Alibaba Cloud CPU control plane and private OSS bucket.
5. Expand ENA BioSample retrieval and reduce synthetic condition coverage.
6. Add a GPU worker only for a measured model-training or inference workload.
