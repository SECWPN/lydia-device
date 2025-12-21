from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AuditConfig:
    path: str
    max_queue: int = 2000
    flush_every: int = 1  # 1 = flush each line; raise if you want throughput


class AuditLogger:
    """
    JSONL audit logger with an async queue and a single writer task.

    Usage:
      audit = AuditLogger(AuditConfig("/var/lib/lydia-device/audit.jsonl"))
      await audit.start()
      audit.log({"kind": "exec", ...})
      ...
      await audit.stop()

    Notes:
      - `log()` is non-blocking (best-effort).
      - If queue is full, events are dropped and a counter is tracked.
    """

    def __init__(self, cfg: AuditConfig):
        self.cfg = cfg
        self._q: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=cfg.max_queue)
        self._task: Optional[asyncio.Task[None]] = None
        self._dropped = 0
        self._pid = os.getpid()

    async def start(self) -> None:
        os.makedirs(os.path.dirname(self.cfg.path) or ".", exist_ok=True)
        if self._task is None:
            self._task = asyncio.create_task(self._run_writer())

    async def stop(self) -> None:
        if self._task is None:
            return
        # signal shutdown
        await self._q.put({"__audit_shutdown__": True})
        await self._task
        self._task = None

    def log(self, event: Dict[str, Any]) -> None:
        """
        Enqueue an audit event (best-effort, non-blocking).

        Adds:
          - ts_ms
          - pid
        """
        enriched = dict(event)
        enriched.setdefault("ts_ms", int(time.time() * 1000))
        enriched.setdefault("pid", self._pid)

        try:
            self._q.put_nowait(enriched)
        except asyncio.QueueFull:
            self._dropped += 1
            # Best-effort: try to record drops without blocking
            try:
                self._q.put_nowait(
                    {
                        "kind": "audit_drop",
                        "ts_ms": int(time.time() * 1000),
                        "pid": self._pid,
                        "dropped_total": self._dropped,
                    }
                )
            except asyncio.QueueFull:
                # If we're totally jammed, accept the drop silently.
                pass

    async def _run_writer(self) -> None:
        flush_count = 0

        # Open in append mode, line-buffered.
        # We keep it open for the lifetime of the process.
        with open(self.cfg.path, "a", encoding="utf-8", buffering=1) as f:
            while True:
                item = await self._q.get()

                if item.get("__audit_shutdown__"):
                    # drain remaining items quickly
                    while not self._q.empty():
                        rest = self._q.get_nowait()
                        if rest.get("__audit_shutdown__"):
                            continue
                        f.write(json.dumps(rest, ensure_ascii=False) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                    return

                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                flush_count += 1

                if flush_count >= self.cfg.flush_every:
                    f.flush()
                    os.fsync(f.fileno())
                    flush_count = 0


# --------------------------------------------------------------------
# Module-level convenience (simple integration)
# --------------------------------------------------------------------

_audit: Optional[AuditLogger] = None


def init_audit(path: str) -> None:
    global _audit
    _audit = AuditLogger(AuditConfig(path=path))


async def start_audit() -> None:
    if _audit is None:
        raise RuntimeError("Audit not initialized. Call init_audit(path) first.")
    await _audit.start()


async def stop_audit() -> None:
    if _audit is None:
        return
    await _audit.stop()


def audit_log(event: Dict[str, Any]) -> None:
    if _audit is None:
        # fail open (don’t crash device comms because audit isn't up)
        return
    _audit.log(event)
