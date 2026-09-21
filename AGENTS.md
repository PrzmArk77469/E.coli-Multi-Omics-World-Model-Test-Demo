# Repository Operations

- Do not commit raw omics data, reference archives, checkpoints, or secrets.
- Do not delete or rewrite data outside this repository without explicit
  approval.
- Every generated artifact must record its source data version, code commit,
  configuration, container image, and random seed.
- Run infrastructure commands through the scripts under `infra/`.
- Keep logs under `logs/`; do not overwrite an existing log from a prior run.
- Do not place SSH private keys, cloud AccessKeys, or API tokens in the
  repository.
- GPU jobs require a maximum runtime, checkpoint destination, and budget tag.
- When changing deployment scripts, update the matching document under `docs/`.

