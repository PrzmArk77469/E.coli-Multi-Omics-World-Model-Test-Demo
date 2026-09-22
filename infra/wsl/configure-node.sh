#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/mnt/d/CodexApp/Project13/Git}"
LOG_DIR="${LOG_DIR:-${REPO_ROOT}/logs}"
TARGET_USER="${TARGET_USER:-mars}"
NODE_MAJOR="${NODE_MAJOR:-22}"
NODE_VERSION="${NODE_VERSION:-v22.23.2}"
NVM_VERSION="${NVM_VERSION:-v0.40.4}"
NVM_REPO="${NVM_REPO:-https://github.com/nvm-sh/nvm.git}"

mkdir -p "${LOG_DIR}"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/node-configure-${STAMP}.log"

exec > >(tee -a "${LOG_FILE}") 2>&1

echo "Configuring Ubuntu Node.js support at $(date -Is)"
echo "Log: ${LOG_FILE}"

if ! id "${TARGET_USER}" >/dev/null 2>&1; then
  echo "Target user does not exist: ${TARGET_USER}" >&2
  exit 1
fi

TARGET_HOME="$(getent passwd "${TARGET_USER}" | awk -F: '{print $6}')"
TARGET_GROUP="$(id -gn "${TARGET_USER}")"
NVM_DIR="${NVM_DIR:-${TARGET_HOME}/.nvm}"

if [[ "$(id -un)" != "${TARGET_USER}" && "${EUID}" -ne 0 ]]; then
  echo "Run this script as ${TARGET_USER} or root." >&2
  exit 1
fi

as_target() {
  if [[ "${EUID}" -eq 0 ]]; then
    runuser -u "${TARGET_USER}" -- env \
      HOME="${TARGET_HOME}" \
      NVM_DIR="${NVM_DIR}" \
      NODE_MAJOR="${NODE_MAJOR}" \
      NODE_VERSION="${NODE_VERSION}" \
      "$@"
  else
    env \
      HOME="${TARGET_HOME}" \
      NVM_DIR="${NVM_DIR}" \
      NODE_MAJOR="${NODE_MAJOR}" \
      NODE_VERSION="${NODE_VERSION}" \
      "$@"
  fi
}

target_bash() {
  as_target bash -lc "$1"
}

run_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "Root privileges are required to create /usr/local/bin links." >&2
    exit 1
  fi
}

if [[ ! -s "${NVM_DIR}/nvm.sh" ]]; then
  echo "Installing nvm ${NVM_VERSION} into ${NVM_DIR}"
  as_target git clone \
    --depth 1 \
    --branch "${NVM_VERSION}" \
    "${NVM_REPO}" \
    "${NVM_DIR}"
else
  echo "nvm is already installed at ${NVM_DIR}"
fi

if ! target_bash 'source "$NVM_DIR/nvm.sh"; nvm version "$NODE_VERSION" >/dev/null 2>&1'; then
  echo "Installing Node.js ${NODE_VERSION}"
  target_bash 'source "$NVM_DIR/nvm.sh"; nvm install "$NODE_VERSION"'
else
  echo "Node.js ${NODE_VERSION} is already installed through nvm"
fi

target_bash 'source "$NVM_DIR/nvm.sh"; nvm alias default "$NODE_VERSION" >/dev/null; nvm use default >/dev/null'

NODE_BIN="$(target_bash 'source "$NVM_DIR/nvm.sh"; nvm which default' |
  awk '/^\// { line = $0 } END { print line }')"
if [[ -z "${NODE_BIN}" || ! -x "${NODE_BIN}" ]]; then
  echo "Unable to resolve the default Node.js executable." >&2
  exit 1
fi

NODE_ROOT="$(cd "$(dirname "${NODE_BIN}")/.." && pwd -P)"
DEFAULT_NODE_VERSION="$(target_bash 'source "$NVM_DIR/nvm.sh"; nvm version default')"

as_target ln -sfn "${NODE_ROOT}" "${NVM_DIR}/current"

for tool in node npm npx corepack; do
  if [[ -e "${NODE_ROOT}/bin/${tool}" || -L "${NODE_ROOT}/bin/${tool}" ]]; then
    desired_link="${NVM_DIR}/current/bin/${tool}"
    current_link="$(readlink "/usr/local/bin/${tool}" 2>/dev/null || true)"
    if [[ "${current_link}" != "${desired_link}" ]]; then
      run_root ln -sfn "${desired_link}" "/usr/local/bin/${tool}"
    fi
  fi
done

add_managed_block() {
  local file="$1"
  local marker="$2"
  local block="$3"

  if [[ ! -e "${file}" ]]; then
    if [[ "${EUID}" -eq 0 ]]; then
      install -m 0644 -o "${TARGET_USER}" -g "${TARGET_GROUP}" /dev/null "${file}"
    else
      : >"${file}"
    fi
  fi

  if ! grep -qF "${marker}" "${file}"; then
    printf '\n%s\n' "${block}" >>"${file}"
  fi

  if [[ "${EUID}" -eq 0 ]]; then
    chown "${TARGET_USER}:${TARGET_GROUP}" "${file}"
  fi
}

read -r -d '' NVM_BLOCK <<'EOF' || true
# >>> project13 nvm >>>
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  . "$NVM_DIR/nvm.sh"
fi
if [ -s "$NVM_DIR/bash_completion" ]; then
  . "$NVM_DIR/bash_completion"
fi
# <<< project13 nvm <<<
EOF

read -r -d '' PROFILE_BLOCK <<'EOF' || true
# >>> project13 bash init >>>
if [ -n "${BASH_VERSION:-}" ] && [ -f "$HOME/.bashrc" ]; then
  . "$HOME/.bashrc"
fi
# <<< project13 bash init <<<
EOF

add_managed_block "${TARGET_HOME}/.bashrc" "# >>> project13 nvm >>>" "${NVM_BLOCK}"
add_managed_block "${TARGET_HOME}/.profile" "# >>> project13 bash init >>>" "${PROFILE_BLOCK}"

system_node="$(env -i \
  HOME="${TARGET_HOME}" \
  PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  bash -c 'command -v node')"
system_node_version="$(env -i \
  HOME="${TARGET_HOME}" \
  PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  bash -c 'node --version')"
system_npm_version="$(env -i \
  HOME="${TARGET_HOME}" \
  PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  bash -c 'npm --version')"

if [[ "${system_node}" != "/usr/local/bin/node" ]]; then
  echo "Node.js is not resolving from /usr/local/bin: ${system_node}" >&2
  exit 1
fi

if [[ "${system_node_version}" != "${NODE_VERSION}" || "${DEFAULT_NODE_VERSION}" != "${NODE_VERSION}" ]]; then
  echo "Expected Node.js ${NODE_VERSION}, got ${system_node_version} (default ${DEFAULT_NODE_VERSION})." >&2
  exit 1
fi

echo "nvm: ${NVM_VERSION}"
echo "Node.js default: ${DEFAULT_NODE_VERSION}"
echo "Node.js executable: ${NODE_BIN}"
echo "Global Node.js: ${system_node}"
echo "Global Node.js version: ${system_node_version}"
echo "Global npm version: ${system_npm_version}"
echo "Node.js configuration completed at $(date -Is)"
