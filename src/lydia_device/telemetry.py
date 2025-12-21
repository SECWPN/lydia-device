from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional, Set

import cbor2

from lydia_device.types import WsLike

from .msh import MshSession
from .parse_status import StatusParsed, parse_status_block


class TelemetryHub:
    """
    Fan-out hub for websocket clients.
    Handles debouncing and safe broadcast.
    """

    def __init__(self) -> None:
        self._clients: Set[WsLike] = set()
        self._lock = asyncio.Lock()
        self._last_fingerprint: Optional[str] = None

    async def add(self, ws: WsLike) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def remove(self, ws: WsLike) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, msg: Dict[str, Any]) -> None:
        """
        Broadcast a CBOR-encoded message to all connected clients.
        Dead sockets are cleaned up automatically.
        """
        payload = cbor2.dumps(msg)
        dead: list[WsLike] = []

        async with self._lock:
            for ws in self._clients:
                try:
                    await ws.send(payload)
                except Exception:
                    dead.append(ws)

            for ws in dead:
                self._clients.discard(ws)

    # ------------------------------
    # Debounce logic
    # ------------------------------

    def _fingerprint(self, parsed: StatusParsed) -> str:
        """
        Generate a stable fingerprint over fields that matter to the UI.
        If this changes, emit a new `status` event.
        """
        core = {
            "work_state": parsed.get("work_state"),
            "work_mode": parsed.get("work_mode"),
            "laser_state": parsed.get("laser_state"),
            "power_out": parsed.get("power_out"),
            "warning": parsed.get("warning"),
            "error": parsed.get("error"),
            "lock": parsed.get("lock"),
            "io_flags": parsed.get("io_flags"),
            "env": parsed.get("env"),
            "pressure": parsed.get("pressure"),
            "tem": parsed.get("tem"),
        }
        return json.dumps(core, sort_keys=True, separators=(",", ":"))

    def changed(self, parsed: StatusParsed) -> bool:
        fp = self._fingerprint(parsed)
        if fp != self._last_fingerprint:
            self._last_fingerprint = fp
            return True
        return False


# ------------------------------------------------------------
# Poll loop
# ------------------------------------------------------------


async def poll_status_loop(
    msh: MshSession,
    hub: TelemetryHub,
    hz: float = 2.0,
) -> None:
    """
    Poll `status` from the device at `hz` (clamped 0.5–5 Hz).

    Emits:
      - event: status     (only when parsed payload changes)
      - event: heartbeat  (every poll, always)
      - event: status_error (on serial / parse failure)

    All events include:
      - ts_ms
      - latency_ms
    """

    hz = max(0.5, min(hz, 5.0))
    period = 1.0 / hz

    while True:
        t0 = time.perf_counter()
        ts_ms = int(time.time() * 1000)

        ok = True
        parsed: Optional[StatusParsed] = None
        err: Optional[str] = None

        try:
            stdout = await msh.exec("status", timeout=5.0)
            parsed = parse_status_block(stdout)
        except Exception as e:
            ok = False
            err = str(e)

        latency_ms = int((time.perf_counter() - t0) * 1000)

        if ok and parsed is not None:
            # Always emit heartbeat for recency / connectivity
            await hub.broadcast(
                {
                    "type": "event",
                    "name": "heartbeat",
                    "ts_ms": ts_ms,
                    "latency_ms": latency_ms,
                }
            )

            # Emit status only on change
            if hub.changed(parsed):
                await hub.broadcast(
                    {
                        "type": "event",
                        "name": "status",
                        "ts_ms": ts_ms,
                        "latency_ms": latency_ms,
                        "parsed": parsed,
                    }
                )
        else:
            await hub.broadcast(
                {
                    "type": "event",
                    "name": "status_error",
                    "ts_ms": ts_ms,
                    "latency_ms": latency_ms,
                    "error": err or "unknown error",
                }
            )

        elapsed = time.perf_counter() - t0
        await asyncio.sleep(max(0.0, period - elapsed))
