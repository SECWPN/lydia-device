import asyncio

import cbor2

from lydia_device.telemetry import TelemetryHub


class FakeWs:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.sent: list[bytes] = []

    async def send(self, data: bytes) -> None:
        if self.should_fail:
            raise RuntimeError("socket closed")
        self.sent.append(data)


def test_telemetry_broadcast_drops_dead_clients() -> None:
    hub = TelemetryHub()
    good = FakeWs()
    bad = FakeWs(should_fail=True)

    async def run() -> None:
        await hub.add(good)
        await hub.add(bad)
        await hub.broadcast({"type": "event", "name": "ping"})

    asyncio.run(run())

    assert good in hub._clients
    assert bad not in hub._clients
    assert cbor2.loads(good.sent[0])["name"] == "ping"


def test_telemetry_changed_only_on_deltas() -> None:
    hub = TelemetryHub()
    baseline = {"work_state": "IDLE", "power_out": {"w": 10}}
    same = {"work_state": "IDLE", "power_out": {"w": 10}}
    updated = {"work_state": "RUN", "power_out": {"w": 10}}

    assert hub.changed(baseline) is True
    assert hub.changed(same) is False
    assert hub.changed(updated) is True
