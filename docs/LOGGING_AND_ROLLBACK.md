# Logging and Rollback

## Logs

Every infrastructure script writes a timestamped transcript under
`D:\CodexApp\Project13\Git\logs`.

Important files:

- `wsl-enable-*.log`: Windows feature changes.
- `ubuntu-install-*.log`: rootfs download and import.
- `docker-desktop-*.log`: Docker Desktop installation.
- `bootstrap-*.log`: Ubuntu package installation.
- `wsl-reboot-required.flag`: reboot marker.

Logs are ignored by Git except for `logs/README.md`.

## Rollback rules

1. Do not delete the repository or the existing `EcoliOmics` data tree.
2. To remove only the imported distro, use `wsl --unregister Ubuntu-24.04`.
3. Before unregistering, export the distro:
   `wsl --export Ubuntu-24.04 D:\WSL\Backups\Ubuntu-24.04-backup.tar`.
4. To stop a broken build, terminate WSL with `wsl --shutdown`.
5. Disable WSL features only if the user explicitly requests it and no other
   WSL distributions depend on them.
6. Docker Desktop can be reinstalled without deleting `D:\DockerDesktopData`.

## Recovery sequence

1. Read the latest timestamped log.
2. Identify the first command that returned a nonzero exit code.
3. Restore the last valid repository commit.
4. Re-run the failed idempotent script.
5. If the distro is damaged, export what remains, unregister it, and re-import
   from the rootfs archive.

