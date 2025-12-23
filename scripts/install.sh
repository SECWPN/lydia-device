#!/usr/bin/env bash
set -euo pipefail

REPO_URL_DEFAULT="https://github.com/SECWPN/lydia-device.git"
REF_DEFAULT="v0.6.0"   # you will update this when you cut releases
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
SERIAL_GROUP=""
SERIAL_DEV_GROUP=""
SERVICE_GROUPS=""
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
  local missing=()
  local pkg
  for pkg in "$@"; do
    if ! dpkg -s "${pkg}" >/dev/null 2>&1; then
      missing+=("${pkg}")
    fi
  done
  if [[ "${#missing[@]}" -eq 0 ]]; then
    log "Packages already installed: $*"
    return
  fi

  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y --no-install-recommends "${missing[@]}"
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

detect_serial_device_group() {
  local gname="" gid=""
  if [[ -e "${SERIAL}" ]]; then
    gname="$(stat -c '%G' "${SERIAL}" 2>/dev/null || true)"
    if [[ -n "${gname}" && "${gname}" =~ ^[0-9]+$ ]]; then
      gid="${gname}"
      gname="$(getent group "${gid}" | cut -d: -f1)"
    fi
  fi
  SERIAL_DEV_GROUP="${gname}"
}

choose_serial_group() {
  if getent group dialout >/dev/null 2>&1; then
    SERIAL_GROUP="dialout"
  elif getent group uucp >/dev/null 2>&1; then
    SERIAL_GROUP="uucp"
  else
    SERIAL_GROUP="${SERIAL_DEV_GROUP}"
  fi
}

append_group() {
  local group="$1"
  [[ -z "${group}" ]] && return
  if [[ " ${SERVICE_GROUPS} " != *" ${group} "* ]]; then
    SERVICE_GROUPS="${SERVICE_GROUPS}${SERVICE_GROUPS:+ }${group}"
  fi
}

install_udev_rule() {
  local udev_info vendor product serial serial_escaped serial_match rule_file
  local new_rule existing_rule

  if [[ -z "${SERIAL_GROUP}" ]]; then
    log "No serial group available; skipping udev rule"
    return
  fi
  if ! getent group "${SERIAL_GROUP}" >/dev/null 2>&1; then
    log "Group ${SERIAL_GROUP} does not exist; skipping udev rule"
    return
  fi
  if ! command -v udevadm >/dev/null 2>&1; then
    log "udevadm not available; skipping udev rule"
    return
  fi
  if [[ ! -e "${SERIAL}" ]]; then
    log "Serial device not present at ${SERIAL}; skipping udev rule"
    return
  fi

  udev_info="$(udevadm info -a -n "${SERIAL}" 2>/dev/null || true)"
  vendor="$(printf '%s\n' "${udev_info}" | awk -F'==' '/ATTRS{idVendor}/ {gsub(/"/,"",$2); gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}')"
  product="$(printf '%s\n' "${udev_info}" | awk -F'==' '/ATTRS{idProduct}/ {gsub(/"/,"",$2); gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}')"
  serial="$(printf '%s\n' "${udev_info}" | awk -F'==' '/ATTRS{serial}/ {gsub(/"/,"",$2); gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}')"

  if [[ -z "${vendor}" || -z "${product}" ]]; then
    log "Unable to determine USB idVendor/idProduct for ${SERIAL}; skipping udev rule"
    return
  fi

  serial_match=""
  if [[ -n "${serial}" ]]; then
    serial_escaped="${serial//\"/\\\"}"
    serial_match=", ATTRS{serial}==\"${serial_escaped}\""
  fi

  rule_file="/etc/udev/rules.d/99-lydia-serial.rules"
  new_rule="SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"${vendor}\", ATTRS{idProduct}==\"${product}\"${serial_match}, GROUP=\"${SERIAL_GROUP}\", MODE=\"0660\""
  if [[ -f "${rule_file}" ]]; then
    existing_rule="$(grep -E 'SUBSYSTEM=="tty".*ATTRS\\{idVendor\\}==".*".*ATTRS\\{idProduct\\}==".*"' "${rule_file}" | tail -n 1 || true)"
    if [[ "${existing_rule}" == "${new_rule}" ]]; then
      log "Udev rule already up to date; skipping"
      return
    fi
  fi

  log "Installing udev rule for ${SERIAL} (group=${SERIAL_GROUP})"
  cat >"${rule_file}" <<EOF
# SECWPN Lydia Device serial permissions
${new_rule}
EOF

  udevadm control --reload-rules
  udevadm trigger --name-match="$(basename "${SERIAL}")" >/dev/null 2>&1 || true
}

prepare_serial_access() {
  detect_serial_device_group
  choose_serial_group
  SERVICE_GROUPS=""
  append_group "${SERIAL_GROUP}"
  append_group "${SERIAL_DEV_GROUP}"
  install_udev_rule
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

  if [[ -n "${SERIAL_GROUP}" ]]; then
    log "Adding ${APP_USER} to ${SERIAL_GROUP} for serial access"
    usermod -a -G "${SERIAL_GROUP}" "${APP_USER}"
  fi
  if [[ -n "${SERIAL_DEV_GROUP}" && "${SERIAL_DEV_GROUP}" != "${SERIAL_GROUP}" ]]; then
    log "Adding ${APP_USER} to ${SERIAL_DEV_GROUP} (current device group)"
    usermod -a -G "${SERIAL_DEV_GROUP}" "${APP_USER}"
  fi
  if [[ -z "${SERIAL_GROUP}" && -z "${SERIAL_DEV_GROUP}" ]]; then
    log "No serial group found; serial access may require manual fix"
  fi
}

install_repo() {
  log "Installing system packages (git, python3, python3-venv)..."
  apt_install git python3 python3-venv
  if [[ -d "${APP_DIR}/.git" ]]; then
    log "Updating existing repo..."
    chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
    sudo -u "${APP_USER}" -H git -C "${APP_DIR}" fetch --all --tags
  else
    rm -rf "${APP_DIR}"
    mkdir -p "${APP_DIR}"
    chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
    sudo -u "${APP_USER}" -H git clone "${REPO_URL}" "${APP_DIR}"
  fi

  if [[ -n "${SHA}" ]]; then
    log "Checking out pinned SHA: ${SHA}"
    sudo -u "${APP_USER}" -H git -C "${APP_DIR}" checkout -f "${SHA}"
  else
    log "Checking out ref: ${REF}"
    sudo -u "${APP_USER}" -H git -C "${APP_DIR}" checkout -f "${REF}"
  fi

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
${SERVICE_GROUPS:+SupplementaryGroups=${SERVICE_GROUPS}}
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
  if tailscale serve --bg "http://${WS_HOST}:${WS_PORT}" >/dev/null 2>&1; then
    return
  fi
  if tailscale serve https / "http://${WS_HOST}:${WS_PORT}" >/dev/null 2>&1; then
    return
  fi
  if tailscale serve https:443 "http://${WS_HOST}:${WS_PORT}" >/dev/null 2>&1; then
    return
  fi
  if tailscale serve --https=443 / "http://${WS_HOST}:${WS_PORT}" >/dev/null 2>&1; then
    return
  fi
  die "Tailscale Serve failed. Run: tailscale serve --help"
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

sudo -u "\${APP_USER}" -H git -C "\${APP_DIR}" fetch --all --tags
if [[ -n "\${SHA}" ]]; then
  sudo -u "\${APP_USER}" -H git -C "\${APP_DIR}" checkout -f "\${SHA}"
else
  sudo -u "\${APP_USER}" -H git -C "\${APP_DIR}" checkout -f "\${REF}"
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
[install]  3) Ensure serial permissions (udev rule + groups)
[install]  4) Create the ${APP_USER} system user
[install]  5) Clone/update ${REPO_URL} into ${APP_DIR}
[install]  6) Install dependencies with uv
[install]  7) Install and start the ${SERVICE_NAME} systemd service
[install]  8) Configure Tailscale Serve to proxy HTTPS to localhost:${WS_PORT}
[install]  9) Install the daily update timer
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
  prepare_serial_access
  create_user
  install_repo
  write_service
  configure_serve
  install_updater
  print_wss
}

main
