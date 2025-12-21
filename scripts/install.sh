#!/usr/bin/env bash
set -euo pipefail

REPO_URL_DEFAULT="https://github.com/SECWPN/lydia-device.git"
REF_DEFAULT="v0.2.0"   # you will update this when you cut releases
APP_DIR="/opt/lydia-device"
APP_USER="lydia-device"
SERVICE_NAME="lydia-device"
WS_PORT="8787"
WS_HOST="127.0.0.1"
BAUD_DEFAULT="115200"

REF="${REF_DEFAULT}"
SHA=""
SERIAL="/dev/ttyUSB0"
HZ="2.0"
REPO_URL="${REPO_URL_DEFAULT}"
ASSUME_YES=0

usage() {
  cat <<EOF
Usage: install.sh [--ref vX.Y.Z] [--sha COMMIT] [--serial /dev/ttyUSB0] [--hz 2.0] [--repo URL] [-y|--yes]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) REF="$2"; shift 2 ;;
    --sha) SHA="$2"; shift 2 ;;
    --serial) SERIAL="$2"; shift 2 ;;
    --hz) HZ="$2"; shift 2 ;;
    --repo) REPO_URL="$2"; shift 2 ;;
    -y|--yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

log(){ echo "[install] $*"; }
die(){ echo "[install] ERROR: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run as root (use: curl ... | sudo bash)"
export PATH="/usr/local/bin:${PATH}"

apt_install() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y --no-install-recommends "$@"
}

require_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing: $1"; }

check_tailscale() {
  log "Checking Tailscale status..."
  require_cmd tailscale
  tailscale status >/dev/null 2>&1 || die "Tailscale not up. Run: sudo tailscale up"
  tailscale serve status >/dev/null 2>&1 || die "tailscale serve unavailable. Update tailscale."
}

install_uv() {
  if command -v uv >/dev/null 2>&1; then
    log "uv present: $(uv --version || true)"
    return
  fi
  log "Installing uv to /usr/local/bin..."
  apt_install curl ca-certificates
  curl -fsSL https://astral.sh/uv/install.sh | UV_INSTALL_DIR="/usr/local/bin" sh
  require_cmd uv
}

create_user() {
  log "Ensuring system user exists: ${APP_USER}"
  if id -u "${APP_USER}" >/dev/null 2>&1; then
    log "User exists: ${APP_USER}"
  else
    useradd --system --create-home --home-dir "/var/lib/${APP_USER}" --shell /usr/sbin/nologin "${APP_USER}"
  fi
  mkdir -p "/var/lib/${APP_USER}"
  chown -R "${APP_USER}:${APP_USER}" "/var/lib/${APP_USER}"
}

install_repo() {
  log "Installing system packages (git, python3, python3-venv)..."
  apt_install git python3 python3-venv
  if [[ -d "${APP_DIR}/.git" ]]; then
    log "Updating existing repo..."
    git -C "${APP_DIR}" fetch --all --tags
  else
    rm -rf "${APP_DIR}"
    git clone "${REPO_URL}" "${APP_DIR}"
  fi

  if [[ -n "${SHA}" ]]; then
    log "Checking out pinned SHA: ${SHA}"
    git -C "${APP_DIR}" checkout -f "${SHA}"
  else
    log "Checking out ref: ${REF}"
    git -C "${APP_DIR}" checkout -f "${REF}"
  fi

  chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

  log "Installing deps with uv..."
  sudo -u "${APP_USER}" -H bash -lc "cd '${APP_DIR}' && uv python install 3.14 && uv python pin 3.14 && uv sync"
}

write_service() {
  log "Installing systemd unit..."

  cat >/etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=SECWPN Lydia Device (MSH over WSS via Tailscale Serve)
After=network-online.target tailscaled.service
Wants=network-online.target tailscaled.service

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=WS_HOST=${WS_HOST}
Environment=WS_PORT=${WS_PORT}
Environment=POLL_HZ=${HZ}
Environment=SERIAL_DEV=${SERIAL}
Environment=BAUD=${BAUD_DEFAULT}
Environment=AUDIT_PATH=/var/lib/${APP_USER}/audit.jsonl
ExecStart=/usr/local/bin/uv run lydia-device
Restart=always
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=${APP_DIR} /var/lib/${APP_USER}
DeviceAllow=${SERIAL} rwm

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now "${SERVICE_NAME}"
}

configure_serve() {
  log "Configuring Tailscale Serve (HTTPS -> localhost:${WS_PORT})"
  tailscale serve reset >/dev/null 2>&1 || true
  tailscale serve https:443 "http://${WS_HOST}:${WS_PORT}"
}

install_updater() {
  log "Installing update script + timer..."

  cat >/usr/local/bin/${SERVICE_NAME}-update <<EOF
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR}"
APP_USER="${APP_USER}"
SERVICE_NAME="${SERVICE_NAME}"
REF="${REF}"
SHA="${SHA}"

git -C "\${APP_DIR}" fetch --all --tags
if [[ -n "\${SHA}" ]]; then
  git -C "\${APP_DIR}" checkout -f "\${SHA}"
else
  git -C "\${APP_DIR}" checkout -f "\${REF}"
fi

sudo -u "\${APP_USER}" -H bash -lc "cd '\${APP_DIR}' && /usr/local/bin/uv sync"
systemctl restart "\${SERVICE_NAME}"
EOF
  chmod +x /usr/local/bin/${SERVICE_NAME}-update

  cat >/etc/systemd/system/${SERVICE_NAME}-update.service <<EOF
[Unit]
Description=Update ${SERVICE_NAME} and restart

[Service]
Type=oneshot
ExecStart=/usr/local/bin/${SERVICE_NAME}-update
EOF

  cat >/etc/systemd/system/${SERVICE_NAME}-update.timer <<EOF
[Unit]
Description=Daily update timer for ${SERVICE_NAME}

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=900

[Install]
WantedBy=timers.target
EOF

  systemctl daemon-reload
  systemctl enable --now ${SERVICE_NAME}-update.timer
}

print_wss() {
  local hn suffix
  hn="$(hostname -s)"
  suffix="$(tailscale status --json | python3 - <<'PY'
import json,sys
j=json.load(sys.stdin)
print((j.get("MagicDNSSuffix") or "").strip())
PY
)"
  [[ -n "${suffix}" ]] || die "MagicDNS not enabled on tailnet. Enable MagicDNS to get stable hostname."
  echo
  echo "wss://${hn}.${suffix}/"
}

announce_plan() {
  cat <<EOF
[install] This installer will:
[install]  1) Verify Tailscale is running and Serve is available
[install]  2) Install uv (Python package manager) to /usr/local/bin
[install]  3) Create the ${APP_USER} system user
[install]  4) Clone/update ${REPO_URL} into ${APP_DIR}
[install]  5) Install dependencies with uv
[install]  6) Install and start the ${SERVICE_NAME} systemd service
[install]  7) Configure Tailscale Serve to proxy HTTPS to localhost:${WS_PORT}
[install]  8) Install the daily update timer
EOF
  log "Repo: ${REPO_URL}"
  if [[ -n "${SHA}" ]]; then
    log "Checkout: ${SHA}"
  else
    log "Checkout: ${REF}"
  fi
  log "Serial device: ${SERIAL}"
  log "Polling rate (Hz): ${HZ}"
}

confirm_or_exit() {
  if [[ "${ASSUME_YES}" -eq 1 ]]; then
    return
  fi
  if [[ -r /dev/tty ]]; then
    local reply
    read -r -p "[install] Proceed? [y/N]: " reply < /dev/tty
    case "${reply}" in
      y|Y|yes|YES) return ;;
      *) die "Aborted." ;;
    esac
  else
    die "No TTY available for confirmation. Re-run with --yes to proceed."
  fi
}

main() {
  announce_plan
  confirm_or_exit
  log "Installing base packages (ca-certificates)..."
  apt_install ca-certificates
  check_tailscale
  install_uv
  create_user
  install_repo
  write_service
  configure_serve
  install_updater
  print_wss
}

main
