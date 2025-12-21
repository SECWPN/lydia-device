# Support

## Scope of support

Support is provided on a **best-effort basis**.

This project is intended for technically proficient users operating
custom hardware.

---

## Before opening an issue

Please collect:

```bash
tailscale status
systemctl status lydia-device
journalctl -u lydia-device --no-pager | tail -n 200
```

Also include:

- Pi OS version
- Serial device path
- Installed tag or commit SHA

## How to get help

- Open a GitHub Issue for bugs or questions
- Use clear, minimal reproductions
- Avoid screenshots of logs; paste text instead

## What is not supported

- Debugging third-party UIs
- Modifying laser firmware
- Circumventing safety or policy checks
- Non-Tailscale networking setups

## Commercial support

- Engage <support@secwpn.com>
