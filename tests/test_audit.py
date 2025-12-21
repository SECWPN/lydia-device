import asyncio
import json

from lydia_device import audit
from lydia_device.audit import AuditConfig, AuditLogger, audit_log


def test_audit_log_noop_before_init() -> None:
    audit_log({"kind": "noop"})


def test_audit_logger_writes_and_drains(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = AuditLogger(AuditConfig(path=str(path), flush_every=100))

    async def run() -> None:
        await audit.start()
        audit.log({"kind": "one"})
        audit.log({"kind": "two"})
        await audit.stop()

    asyncio.run(run())

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    kinds = [json.loads(line)["kind"] for line in lines]
    assert kinds == ["one", "two"]


def test_audit_flush_every(monkeypatch, tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    fsync_calls: list[int] = []
    flush_event = asyncio.Event()

    def _fsync(fd: int) -> None:
        fsync_calls.append(fd)
        if not flush_event.is_set():
            flush_event.set()

    monkeypatch.setattr(audit.os, "fsync", _fsync)

    logger = AuditLogger(AuditConfig(path=str(path), flush_every=2))

    async def run() -> None:
        await logger.start()
        logger.log({"kind": "one"})
        logger.log({"kind": "two"})
        await asyncio.wait_for(flush_event.wait(), timeout=1.0)
        await logger.stop()

    asyncio.run(run())

    assert len(fsync_calls) >= 2
