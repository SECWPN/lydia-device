# Security Policy

## Supported versions

Only the **latest released tag** is supported for security fixes.

Older versions may receive fixes at maintainer discretion but should not
be relied upon.

---

## Threat model

This project assumes:

- The device runs on a **private Tailscale network**
- All WSS connections are authenticated by the tailnet
- Physical safety systems are external and authoritative

Primary risks addressed:

- Unauthorized command execution
- Accidental energizing via UI
- Silent state desynchronization

---

## Reporting a vulnerability

Please **do not open a public issue** for security concerns.

Instead:

- Use GitHub’s private security advisory feature, or
- Contact the maintainer directly (see repository profile)

Include:

- Version / tag
- Description of the issue
- Reproduction steps
- Potential impact

---

## Non-goals

- This project does not attempt to harden the underlying RT-Thread firmware
- Physical tampering is out of scope
