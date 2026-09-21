#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="/mnt/d/CodexApp/Project13/Git/logs"
APT_MIRROR="${APT_MIRROR:-https://mirrors.aliyun.com/ubuntu/}"
mkdir -p "${LOG_DIR}"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/bootstrap-${STAMP}.log"

exec > >(tee -a "${LOG_FILE}") 2>&1

echo "Starting Ubuntu bootstrap at $(date -Is)"

export DEBIAN_FRONTEND=noninteractive

echo "Configuring APT mirror: ${APT_MIRROR}"
install -d -m 0755 /etc/apt/sources.list.d
if [[ -f /etc/apt/sources.list && ! -f /etc/apt/sources.list.codex-disabled ]]; then
  mv /etc/apt/sources.list /etc/apt/sources.list.codex-disabled
fi

cat >/etc/apt/sources.list.d/ubuntu.sources <<EOF
Types: deb
URIs: ${APT_MIRROR}
Suites: noble noble-updates noble-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: ${APT_MIRROR}
Suites: noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF

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

update_ok=0
for attempt in 1 2 3; do
  echo "APT update attempt ${attempt}/3"
  if apt-get -o Acquire::Retries=5 update; then
    update_ok=1
    break
  fi
  sleep $((attempt * 5))
  rm -rf /var/lib/apt/lists/*
done
if [[ "${update_ok}" -ne 1 ]]; then
  echo "APT update failed after 3 attempts." >&2
  exit 1
fi

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

mkdir -p /home/mars/.ssh
chown -R mars:mars /home/mars/.ssh
chmod 700 /home/mars/.ssh

echo "Ubuntu bootstrap completed at $(date -Is)"
echo "Set the Linux password from Windows with:"
echo "wsl.exe -d Ubuntu-24.04 -u root -- passwd mars"
