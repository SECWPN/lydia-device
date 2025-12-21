import json
import sys
from pathlib import Path

import cbor2
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _stub_cbor2(monkeypatch):
    def _dumps(obj) -> bytes:
        return json.dumps(obj, separators=(",", ":")).encode("utf-8")

    def _loads(data):
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        return json.loads(data)

    monkeypatch.setattr(cbor2, "dumps", _dumps)
    monkeypatch.setattr(cbor2, "loads", _loads)
    yield
