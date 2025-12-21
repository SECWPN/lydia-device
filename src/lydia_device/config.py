from __future__ import annotations

import argparse
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    serial_dev: str
    baud: int
    ws_host: str
    ws_port: int
    poll_hz: float
    audit_path: str


def load_config(argv: list[str] | None = None) -> Config:
    p = argparse.ArgumentParser(prog="lydia-device")
    p.add_argument("--serial", default=os.getenv("SERIAL_DEV", "/dev/ttyUSB0"))
    p.add_argument("--baud", type=int, default=int(os.getenv("BAUD", "115200")))
    p.add_argument("--host", default=os.getenv("WS_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("WS_PORT", "8787")))
    p.add_argument("--hz", type=float, default=float(os.getenv("POLL_HZ", "2.0")))
    p.add_argument(
        "--audit", default=os.getenv("AUDIT_PATH", "/var/lib/lydia-device/audit.jsonl")
    )
    a = p.parse_args(argv)

    hz = max(0.5, min(a.hz, 5.0))
    return Config(
        serial_dev=a.serial,
        baud=a.baud,
        ws_host=a.host,
        ws_port=a.port,
        poll_hz=hz,
        audit_path=a.audit,
    )
