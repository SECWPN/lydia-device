# lydia-device

**SECWPN Lydia Device** is a production-grade bridge that exposes a laser controller’s
RT-Thread MSH serial interface over **secure WebSockets (WSS)** using **Tailscale Serve**.

It is designed for **telemetry-first remote observability**, with a tightly controlled
command surface and explicit safety boundaries.

---

## What this is

- A **prompt-delimited serial bridge** for RT-Thread MSH
- A **push-based telemetry server** (`status`, `heartbeat`)
- A **policy-gated command plane** (read-only by default)
- A **reboot-proof system service** for Raspberry Pi
- A **zero-certificate-pain WSS endpoint** via Tailscale

This is **not** a generic remote terminal.
It is a structured, auditable interface intended for real hardware.

---

## Safety model (important)

- **Physical interlocks and grounding remain authoritative**
- The software layer:
  - **Blocks all energizing verbs** (`laser_en`, `onkey`, `power`, etc.)
  - Allows **telemetry getters**
  - Allows **audited setters with parameters** only where explicitly permitted
- All commands are:
  - Serialized
  - Policy-checked
  - Logged to a JSONL audit file

This design intentionally prevents a browser UI from becoming a control pendant.

---

## Architecture overview

Browser UI
│
│ wss://<device>.<tailnet>.ts.net
▼
WebSocket Server (lydia-device)
│
│ serialized exec + polling
▼
RT-Thread MSH (UART / USB serial)

- One authoritative poll loop (`status` at 0.5–5 Hz)
- Many concurrent read-only viewers
- Prompt-based framing (`msh >`)

---

## Installation (Raspberry Pi)

### Prerequisites

- Raspberry Pi OS (Bookworm or Bullseye)
- `tailscale` installed and authenticated:
- `sudo tailscale up`

MagicDNS enabled in your tailnet

## One-line install

```bash
curl -fsSL https://lydia.secwpn.com/install.sh | sudo bash
```

## Optional flags

```bash
curl -fsSL https://lydia.secwpn.com/install.sh | sudo bash -s -- \
  --ref v0.6.0 \
  --serial /dev/ttyUSB0 \
  --hz 2

Supported flags:

--ref vX.Y.Z – install a specific release tag (recommended)
--sha <commit> – pin to an exact commit
--serial /dev/ttyUSB0
--hz 0.5–5.0
```

The installer will print the final wss://… address on completion.

## Runtime behavior

Runs as a dedicated system user

- Managed by systemd
- Auto-restarts on failure
- Daily auto-update timer (ref or SHA-pinned)

### Logs

```bash
journalctl -u lydia-device
```

### Audit log

```bash
/var/lib/lydia-device/audit.jsonl
```

### Development

```bash
uv python pin 3.14
uv sync
uv run lydia-device --serial /dev/ttyUSB0
```

## Non-goals

- Replacing hardware safety systems
- Unauthenticated remote control
- Browser-side LAN discovery
- Chrome-only APIs (Web Serial, etc.)
