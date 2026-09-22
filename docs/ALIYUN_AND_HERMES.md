# Alibaba Cloud and NemoHermes

## Order of operations

The local WSL, Ubuntu, Docker, Git, and proxy foundation is now operational.
Continue with the cloud work below; do not rebuild the local runtime.

1. Create or verify the Alibaba Cloud account and budget guardrails.
2. Create a private OSS bucket in Shanghai or Hangzhou.
3. Create a small CPU ECS control plane with SSH restricted to the current
   public IP.
4. Verify Git, Docker, `uv`, `ossutil`, and `tmux` on the control plane.
5. Add the GPU ECS worker only for a measured workload.
6. Install NemoHermes after the local WSL and Git workflow is stable.

## Remote invocation model

The cloud host is not another local WSL distribution. It is accessed through a
standard Linux remote interface:

```text
Windows Codex
  -> wsl.exe -d Ubuntu-24.04
  -> ssh ecoli-cpu
  -> ssh ecoli-gpu through ProxyJump
```

Use `~/.ssh/config`, `rsync`, `tmux`, and Docker commands from WSL. Long jobs
must run in `tmux` or systemd and write checkpoints to OSS.

## NemoHermes

NemoHermes is an experimental agent layer. It may assist with task planning,
rule drafting, log summaries, and workflow orchestration, but it must not be
the only holder of cloud credentials or the source of scientific state.
