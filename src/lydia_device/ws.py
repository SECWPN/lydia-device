from __future__ import annotations

import time
from typing import Any, Dict

import cbor2
import websockets

from lydia_device.types import WsLike

from .policy import is_allowed
from .parse_getall import parse_getall_block
from .parse_process import parse_process_block
from .parse_status import parse_status_block
from .audit import audit_log
from .telemetry import TelemetryHub
from .config import Config


async def ws_handler(
    ws: WsLike,
    msh,
    hub: TelemetryHub,
    cfg: Config,
) -> None:
    """
    WebSocket command plane.

    Supported messages:
      - {type: "exec", id, cmd}
      - {type: "subscribe"}  (currently a no-op; telemetry is global)

    All execs are:
      - policy-gated
      - serialized by MshSession
      - audited
    """

    await hub.add(ws)
    audit_log({"kind": "connect"})
    try:
        stdout = await msh.exec("getall", timeout=5.0)
        parsed = parse_getall_block(stdout)
        await ws.send(
            cbor2.dumps(
                {
                    "type": "event",
                    "name": "getall",
                    "ts_ms": int(time.time() * 1000),
                    "parsed": parsed,
                }
            )
        )
    except Exception as e:
        await ws.send(
            cbor2.dumps(
                {
                    "type": "event",
                    "name": "getall_error",
                    "ts_ms": int(time.time() * 1000),
                    "error": str(e),
                }
            )
        )

    try:
        async for raw in ws:
            msg = cbor2.loads(raw)
            mtype = msg.get("type")

            # ----------------------------
            # Subscribe (telemetry)
            # ----------------------------
            if mtype == "subscribe":
                await ws.send(
                    cbor2.dumps(
                        {
                            "type": "ack",
                            "op": "subscribe",
                        }
                    )
                )
                continue

            # ----------------------------
            # Exec (command)
            # ----------------------------
            if mtype != "exec":
                await ws.send(
                    cbor2.dumps(
                        {
                            "type": "error",
                            "error": f"Unknown message type: {mtype}",
                        }
                    )
                )
                continue

            req_id = msg.get("id")
            cmd = msg.get("cmd", "")

            allowed, reason = is_allowed(cmd)
            audit_log(
                {
                    "kind": "exec",
                    "cmd": cmd,
                    "allowed": allowed,
                    "reason": reason,
                }
            )

            if not allowed:
                await ws.send(
                    cbor2.dumps(
                        {
                            "type": "result",
                            "id": req_id,
                            "ok": False,
                            "error": "Command not allowed by policy",
                            "reason": reason,
                        }
                    )
                )
                continue

            t0 = time.perf_counter()
            try:
                stdout = await msh.exec(cmd, timeout=5.0)
                latency_ms = int((time.perf_counter() - t0) * 1000)

                parsed = None
                verb = cmd.strip().split()[0].lower()
                if verb == "status":
                    parsed = parse_status_block(stdout)
                elif verb in {"cur_pro", "feeder_pro"}:
                    parsed = parse_process_block(stdout)
                elif verb == "getall":
                    parsed = parse_getall_block(stdout)

                await ws.send(
                    cbor2.dumps(
                        {
                            "type": "result",
                            "id": req_id,
                            "ok": True,
                            "stdout": stdout,
                            "parsed": parsed,
                            "latency_ms": latency_ms,
                            "ts_ms": int(time.time() * 1000),
                        }
                    )
                )

            except Exception as e:
                await ws.send(
                    cbor2.dumps(
                        {
                            "type": "result",
                            "id": req_id,
                            "ok": False,
                            "error": str(e),
                            "ts_ms": int(time.time() * 1000),
                        }
                    )
                )

    finally:
        await hub.remove(ws)
        audit_log({"kind": "disconnect"})
