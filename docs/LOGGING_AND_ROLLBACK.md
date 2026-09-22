# Logging and Rollback

## Logs

Every infrastructure script writes a timestamped transcript under
`D:\CodexApp\Project13\Git\logs`.

Important files:

- `wsl-enable-*.log`: Windows feature changes.
- `ubuntu-install-*.log`: rootfs download and import.
- `docker-desktop-*.log`: Docker Desktop installation.
- `bootstrap-*.log`: Ubuntu package installation.
- `wsl-configure-*.log`: `.wslconfig` and Ubuntu start verification.
- `wsl-2.7.14-install.log`: signed Microsoft WSL runtime installation.
- `hermes-install-*.log`: official Hermes installer download, SHA256,
  dependency installation, update, and diagnostics.
- `verify-*.log` and `last-verification.json`: final infrastructure checks.
- `condition-demo-*.json`: hashes and outcome totals for a condition-aware
  simulation run; the matching event and manifest files remain in the data
  tree.
- `wsl-reboot-required.flag`: transient reboot marker; remove it after the
  reboot has completed and WSL is verified.

Logs are ignored by Git except for `logs/README.md`.

## Rollback rules

1. Do not delete the repository or the existing `EcoliOmics` data tree.
2. To remove only the imported distro, use `wsl --unregister Ubuntu-24.04`.
3. Before unregistering, export the distro:
   `wsl --export Ubuntu-24.04 D:\WSL\Backups\Ubuntu-24.04-backup.tar`.
4. Do not use automated `wsl --shutdown` or `wsl --terminate` calls on this
   Windows 10 host. The legacy service can remain in `STOP_PENDING`.
5. If `LxssManager` is stuck, verify that its service host contains no other
   services with `tasklist /svc /FI "PID eq <pid>"` before restarting only that
   host. Reboot Windows if the service cannot be recovered safely.
6. Disable WSL features only if the user explicitly requests it and no other
   WSL distributions depend on them.
7. Docker Desktop can be reinstalled without deleting `D:\DockerDesktopData`.
8. The WSL runtime MSI must be verified against official SHA256
   `db084e536279a59e90a26ec598d8aa8a4dff8309f41d078fd06242953ac1ebcd`
   and a valid Microsoft Authenticode signature.
9. Hermes code can be recovered through its Git checkout under
   `~/.hermes/hermes-agent`. State and configuration can be backed up with
   `hermes backup` and restored with `hermes import`.
10. Do not replace the official Hermes Agent with an unrelated agent stack
   while the current installation is diagnostically healthy.

## Recovery sequence

1. Read the latest timestamped log.
2. Identify the first command that returned a nonzero exit code.
3. Restore the last valid repository commit.
4. Re-run the failed idempotent script.
5. If the distro is damaged, export what remains, unregister it, and re-import
   from the rootfs archive.
6. If Docker cannot pull because port `7897` is closed, start Clash Verge
   before rerunning the Docker script or verification.
7. If Hermes is missing or damaged, re-run
   `bash infra/wsl/install-hermes.sh`; restore `~/.hermes` from a backup only
   when local sessions, memory, or configuration are also affected.
