from lydia_device.config import load_config


def test_poll_hz_clamps_low() -> None:
    cfg = load_config(["--hz", "0.1"])
    assert cfg.poll_hz == 0.5


def test_poll_hz_clamps_high() -> None:
    cfg = load_config(["--hz", "10.0"])
    assert cfg.poll_hz == 5.0


def test_env_defaults(monkeypatch) -> None:
    monkeypatch.setenv("SERIAL_DEV", "/dev/ttyS1")
    monkeypatch.setenv("BAUD", "9600")
    monkeypatch.setenv("WS_HOST", "0.0.0.0")
    monkeypatch.setenv("WS_PORT", "9999")
    monkeypatch.setenv("POLL_HZ", "3.5")
    monkeypatch.setenv("AUDIT_PATH", "/tmp/audit.jsonl")

    cfg = load_config([])

    assert cfg.serial_dev == "/dev/ttyS1"
    assert cfg.baud == 9600
    assert cfg.ws_host == "0.0.0.0"
    assert cfg.ws_port == 9999
    assert cfg.poll_hz == 3.5
    assert cfg.audit_path == "/tmp/audit.jsonl"
