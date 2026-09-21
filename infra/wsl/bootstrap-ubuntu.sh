#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="/mnt/d/CodexApp/Project13/Git/logs"
mkdir -p "${LOG_DIR}"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/bootstrap-${STAMP}.log"

exec > >(tee -a "${LOG_FILE}") 2>&1

echo "Starting Ubuntu bootstrap at $(date -Is)"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  build-essential \
  ca-certificates \
  curl \
  git \
  jq \
  less \
  openssh-client \
  python3 \
  python3-pip \
  python3-venv \
  rsync \
  software-properties-common \
  sudo \
  systemd \
  tmux \
  unzip \
  vim \
  wget

if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install --break-system-packages --no-cache-dir uv
fi

mkdir -p /home/mars/.ssh
chown -R mars:mars /home/mars/.ssh
chmod 700 /home/mars/.ssh

echo "Ubuntu bootstrap completed at $(date -Is)"
echo "Set the Linux password from Windows with:"
echo "wsl.exe -d Ubuntu-24.04 -u root -- passwd mars"
