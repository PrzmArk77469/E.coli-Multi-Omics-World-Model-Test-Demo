#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/mnt/d/CodexApp/Project13/Git}"
LOG_DIR="${LOG_DIR:-${REPO_ROOT}/logs}"
APT_HTTP_MIRROR="${APT_HTTP_MIRROR:-http://mirrors.aliyun.com/ubuntu/}"
APT_HTTPS_MIRROR="${APT_HTTPS_MIRROR:-https://mirrors.aliyun.com/ubuntu/}"
mkdir -p "${LOG_DIR}"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/bootstrap-${STAMP}.log"

exec > >(tee -a "${LOG_FILE}") 2>&1

echo "Starting Ubuntu bootstrap at $(date -Is)"

export DEBIAN_FRONTEND=noninteractive

install -d -m 0755 /etc/apt/sources.list.d
if [[ -f /etc/apt/sources.list && ! -f /etc/apt/sources.list.codex-disabled ]]; then
  mv /etc/apt/sources.list /etc/apt/sources.list.codex-disabled
fi

write_apt_sources() {
  local mirror="$1"
  cat >/etc/apt/sources.list.d/ubuntu.sources <<EOF
Types: deb
URIs: ${mirror}
Suites: noble noble-updates noble-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: ${mirror}
Suites: noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
}

update_apt() {
  local label="$1"
  local update_ok=0
  for attempt in 1 2 3; do
    echo "APT update (${label}) attempt ${attempt}/3"
    if apt-get -o Acquire::Retries=5 update; then
      update_ok=1
      break
    fi
    sleep $((attempt * 5))
    rm -rf /var/lib/apt/lists/*
  done
  if [[ "${update_ok}" -ne 1 ]]; then
    echo "APT update (${label}) failed after 3 attempts." >&2
    return 1
  fi
}

cat >/etc/apt/apt.conf.d/99-project-network <<'EOF'
Acquire::Retries "5";
Acquire::http::Pipeline-Depth "0";
Acquire::https::Pipeline-Depth "0";
Acquire::http::No-Cache "true";
Acquire::https::No-Cache "true";
Acquire::ForceIPv4 "true";
EOF

apt-get clean
rm -rf /var/lib/apt/lists/*

echo "Bootstrapping CA certificates over HTTP: ${APT_HTTP_MIRROR}"
write_apt_sources "${APT_HTTP_MIRROR}"
update_apt "HTTP bootstrap"

ca_ok=0
for attempt in 1 2 3; do
  echo "CA certificate installation attempt ${attempt}/3"
  if apt-get -y -o Acquire::Retries=5 -o Dpkg::Lock::Timeout=120 install ca-certificates; then
    ca_ok=1
    break
  fi
  apt-get clean
  rm -rf /var/lib/apt/lists/partial/*
  sleep $((attempt * 5))
done
if [[ "${ca_ok}" -ne 1 ]]; then
  echo "CA certificate installation failed after 3 attempts." >&2
  exit 1
fi
update-ca-certificates

echo "Switching APT to HTTPS: ${APT_HTTPS_MIRROR}"
write_apt_sources "${APT_HTTPS_MIRROR}"
apt-get clean
rm -rf /var/lib/apt/lists/*
update_apt "HTTPS"

packages=(
  build-essential
  ca-certificates
  curl
  git
  jq
  less
  openssh-client
  python3
  python3-pip
  python3-venv
  rsync
  software-properties-common
  sudo
  systemd
  tmux
  unzip
  vim
  wget
)

install_ok=0
for attempt in 1 2 3; do
  echo "Package installation attempt ${attempt}/3"
  if apt-get -y -o Acquire::Retries=5 -o Dpkg::Lock::Timeout=120 install "${packages[@]}"; then
    install_ok=1
    break
  fi
  apt-get clean
  rm -rf /var/lib/apt/lists/partial/*
  sleep $((attempt * 5))
done
if [[ "${install_ok}" -ne 1 ]]; then
  echo "Package installation failed after 3 attempts." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install \
    --break-system-packages \
    --no-cache-dir \
    --index-url https://mirrors.aliyun.com/pypi/simple/ \
    uv
fi

echo "Configuring Node.js through nvm"
bash "${REPO_ROOT}/infra/wsl/configure-node.sh"

mkdir -p /home/mars/.ssh
chown -R mars:mars /home/mars/.ssh
chmod 700 /home/mars/.ssh

echo "Ubuntu bootstrap completed at $(date -Is)"
echo "Set the Linux password from Windows with:"
echo "wsl.exe -d Ubuntu-24.04 -u root -- passwd mars"
