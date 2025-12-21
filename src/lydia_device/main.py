from __future__ import annotations

import asyncio

import websockets

from .audit import init_audit, start_audit, stop_audit
from .config import load_config
from .msh import MshSession
from .telemetry import TelemetryHub, poll_status_loop
from .ws import ws_handler


def main_cli() -> None:
    asyncio.run(_amain())


async def _amain() -> None:
    cfg = load_config()
    init_audit(cfg.audit_path)
    await start_audit()

    msh = MshSession(cfg.serial_dev, cfg.baud)
    await msh.connect()

    hub = TelemetryHub()
    poll_task = asyncio.create_task(poll_status_loop(msh, hub, hz=cfg.poll_hz))

    try:
        async with websockets.serve(
            lambda ws: ws_handler(ws, msh, hub, cfg),
            cfg.ws_host,
            cfg.ws_port,
            max_size=None,
            ping_interval=20,
        ):
            await asyncio.Future()
    finally:
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass
        await stop_audit()
