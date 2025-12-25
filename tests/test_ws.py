import asyncio

import cbor2

from lydia_device.config import Config
from lydia_device.telemetry import TelemetryHub
from lydia_device.ws import ws_handler


class FakeWs:
    def __init__(self, incoming: list[bytes]) -> None:
        self._incoming = list(incoming)
        self.sent: list[bytes] = []

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        if not self._incoming:
            raise StopAsyncIteration
        return self._incoming.pop(0)

    async def send(self, data: bytes) -> None:
        self.sent.append(data)


class FakeMsh:
    def __init__(self, responses: dict[str, str] | None = None) -> None:
        base = {"getall": "msh >\n"}
        if responses:
            base.update(responses)
        self.responses = base
        self.calls: list[str] = []

    async def exec(self, cmd: str, timeout: float = 5.0) -> str:
        self.calls.append(cmd)
        if cmd not in self.responses:
            raise AssertionError(f"Unexpected exec: {cmd}")
        return self.responses[cmd]


def _cfg() -> Config:
    return Config(
        serial_dev="/dev/null",
        baud=115200,
        ws_host="127.0.0.1",
        ws_port=8787,
        poll_hz=1.0,
        audit_path="/tmp/audit.jsonl",
    )


def _strip_getall_events(messages: list[bytes]) -> list[dict]:
    decoded = [cbor2.loads(m) for m in messages]
    return [
        m
        for m in decoded
        if not (m.get("type") == "event" and m.get("name") in {"getall", "getall_error"})
    ]


def test_ws_subscribe_ack() -> None:
    ws = FakeWs([cbor2.dumps({"type": "subscribe"})])
    msh = FakeMsh()
    hub = TelemetryHub()

    async def run() -> None:
        await ws_handler(ws, msh, hub, _cfg())

    asyncio.run(run())

    msgs = _strip_getall_events(ws.sent)
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg["type"] == "ack"
    assert msg["op"] == "subscribe"


def test_ws_unknown_type_error() -> None:
    ws = FakeWs([cbor2.dumps({"type": "wat"})])
    msh = FakeMsh()
    hub = TelemetryHub()

    async def run() -> None:
        await ws_handler(ws, msh, hub, _cfg())

    asyncio.run(run())

    msgs = _strip_getall_events(ws.sent)
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg["type"] == "error"
    assert "Unknown message type" in msg["error"]


def test_ws_disallowed_command() -> None:
    ws = FakeWs([cbor2.dumps({"type": "exec", "id": 1, "cmd": "reboot"})])
    msh = FakeMsh()
    hub = TelemetryHub()

    async def run() -> None:
        await ws_handler(ws, msh, hub, _cfg())

    asyncio.run(run())

    msgs = _strip_getall_events(ws.sent)
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg["type"] == "result"
    assert msg["ok"] is False
    assert "not allowed" in msg["error"].lower()
    assert msh.calls == ["getall"]


def test_ws_exec_status_parses() -> None:
    status_text = "Work Mode: AUTO\nWork State: IDLE\nmsh >\n"
    ws = FakeWs([cbor2.dumps({"type": "exec", "id": 2, "cmd": "status"})])
    msh = FakeMsh(responses={"status": status_text})
    hub = TelemetryHub()

    async def run() -> None:
        await ws_handler(ws, msh, hub, _cfg())

    asyncio.run(run())

    msgs = _strip_getall_events(ws.sent)
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg["type"] == "result"
    assert msg["ok"] is True
    assert msg["parsed"]["work_mode"] == "AUTO"
    assert msg["parsed"]["work_state"] == "IDLE"
