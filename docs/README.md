# Documentation Index

## Start here

- [System architecture](SYSTEM_ARCHITECTURE.md): full system structure,
  execution flow, data provenance, deployment boundary, and review checklist.
- [New conversation context](NEW_CONVERSATION_CONTEXT.md): concise handoff for
  a new Codex conversation.
- [Deployment status](DEPLOYMENT_STATUS.md): what is implemented and what is
  still planned.

## Demo and simulation

- [Minimal simulation MVP](SIMULATION_MVP.md): 2,000-agent event-engine design.
- [Condition mapping](CONDITION_MAPPING.md): stable sample and condition IDs.
- [Synthetic conditions](SYNTHETIC_CONDITIONS.md): isolated gap filling,
  provenance rules, and the complete Demo command.
- [Schema index](../schemas/README.md): five core entity schemas.

## Infrastructure

- [Portable infrastructure guide](PORTABLE_INFRASTRUCTURE.md): self-contained
  migration guide for recreating the local stack in a new project without
  copying the current Git history or remotes.
- [Infrastructure topology](INFRASTRUCTURE.md): Windows, WSL, Docker, and cloud
  layout.
- [WSL2 Ubuntu 24.04](WSL2_UBUNTU24.04.md): local runtime deployment.
- [Hermes Agent in WSL](HERMES_WSL.md): official Nous Research installation,
  authentication, operation, and rollback.
- [Network and proxy](NETWORK_AND_PROXY.md): Clash, WSL, Docker, and GitHub
  routing.
- [Logging and rollback](LOGGING_AND_ROLLBACK.md): logs and recovery rules.
- [Alibaba Cloud and Hermes Agent](ALIYUN_AND_HERMES.md): local agent
  connection and planned remote extension path.

## Source design documents

- [Project design documents](project/): the original feasibility studies,
  cloud plans, data-download plans, and E. coli Demo designs.
- [Early visualizations](../visualizations/): feasibility, spectral-mapping,
  and replay HTML pages.
