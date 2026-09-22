#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID}" -eq 0 ]; then
    echo "Run this script as the desktop user, not root." >&2
    exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
block_file="${script_dir}/project13-proxy.bashrc"
bashrc="${HOME}/.bashrc"
begin_marker="# >>> Project13 WSL proxy >>>"

if [ ! -f "${block_file}" ]; then
    echo "Proxy block file not found: ${block_file}" >&2
    exit 1
fi

if [ ! -f "${bashrc}" ]; then
    touch "${bashrc}"
fi

if grep -qF "${begin_marker}" "${bashrc}"; then
    echo "Project13 proxy block is already present in ${bashrc}."
    exit 0
fi

stamp="$(date +%Y%m%d-%H%M%S)"
backup="${bashrc}.project13-backup-${stamp}"
tmp="$(mktemp "${bashrc}.project13.XXXXXX")"
trap 'rm -f "${tmp}"' EXIT

cp -p "${bashrc}" "${backup}"
awk -v block_file="${block_file}" '
    NR == 1 {
        while ((getline line < block_file) > 0) {
            print line
        }
        close(block_file)
        print ""
    }
    { print }
' "${bashrc}" > "${tmp}"

chmod --reference="${bashrc}" "${tmp}"
mv "${tmp}" "${bashrc}"
trap - EXIT

echo "Installed Project13 proxy block in ${bashrc}."
echo "Backup created at ${backup}."
