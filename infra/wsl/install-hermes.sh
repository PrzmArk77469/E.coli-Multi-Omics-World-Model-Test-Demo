#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
LOG_DIR="${LOG_DIR:-${REPO_ROOT}/logs}"
HERMES_INSTALL_URL="${HERMES_INSTALL_URL:-https://hermes-agent.nousresearch.com/install.sh}"
HERMES_INSTALLER_SHA256="${HERMES_INSTALLER_SHA256:-00f9080c6452bf87f03ef2fffb4b2c23b9f43f946aaae956e4c547d17e310b22}"

UPDATE_REQUESTED=false
if [[ "${1:-}" == "--update" ]]; then
  UPDATE_REQUESTED=true
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--update]" >&2
  exit 2
fi

mkdir -p "${LOG_DIR}"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/hermes-install-${STAMP}.log"

exec > >(tee -a "${LOG_FILE}") 2>&1

echo "Starting Nous Research Hermes Agent installation at $(date -Is)"
echo "Log: ${LOG_FILE}"

export DEBIAN_FRONTEND=noninteractive
export PATH="/usr/local/bin:${HOME}/.local/bin:${PATH}"

bash "${REPO_ROOT}/infra/wsl/configure-node.sh"

missing_packages=()
for package in \
  build-essential \
  ca-certificates \
  curl \
  ffmpeg \
  git \
  libffi-dev \
  python3-dev \
  ripgrep; do
  if ! dpkg-query -W -f='${Status}' "${package}" 2>/dev/null |
    grep -q "install ok installed"; then
    missing_packages+=("${package}")
  fi
done

if [[ ${#missing_packages[@]} -gt 0 ]]; then
  echo "Installing Hermes system dependencies: ${missing_packages[*]}"
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends "${missing_packages[@]}"
fi

installer_path="${TMPDIR:-/tmp}/hermes-agent-install.sh"
echo "Downloading official installer: ${HERMES_INSTALL_URL}"
curl --fail --silent --show-error --location \
  --proto '=https' \
  --tlsv1.2 \
  --output "${installer_path}" \
  "${HERMES_INSTALL_URL}"

actual_sha256="$(sha256sum "${installer_path}" | awk '{print $1}')"
echo "Installer SHA256: ${actual_sha256}"
if [[ "${actual_sha256}" != "${HERMES_INSTALLER_SHA256}" ]]; then
  echo "Refusing to run an installer whose SHA256 does not match the reviewed revision." >&2
  echo "Expected: ${HERMES_INSTALLER_SHA256}" >&2
  echo "Actual:   ${actual_sha256}" >&2
  echo "Review the upstream change, then set HERMES_INSTALLER_SHA256 explicitly." >&2
  exit 1
fi

if command -v hermes >/dev/null 2>&1; then
  echo "Hermes Agent is already installed."
  hermes --version
  if [[ "${UPDATE_REQUESTED}" == true ]]; then
    echo "Updating Hermes Agent through its official updater."
    hermes update --yes
  fi
else
  echo "Running the official installer with setup skipped."
  CI=1 bash "${installer_path}" --skip-setup
fi

if ! command -v hermes >/dev/null 2>&1; then
  echo "hermes was not added to PATH. Expected entry point: ${HOME}/.local/bin/hermes" >&2
  exit 1
fi

hermes --version
hermes doctor --fix || true
hermes doctor || true

echo "Hermes Agent installation workflow completed at $(date -Is)"
echo "Model authentication is intentionally not modified by this script."
echo "Run 'hermes setup --portal' or 'hermes model' to configure inference."
