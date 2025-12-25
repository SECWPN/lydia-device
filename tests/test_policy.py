from lydia_device.policy import is_allowed


def test_policy_blocks_multiline() -> None:
    allowed, reason = is_allowed("status\nreboot")
    assert not allowed
    assert "multiline" in reason.lower()


def test_policy_blocks_semicolon() -> None:
    allowed, reason = is_allowed("status; reboot")
    assert not allowed
    assert "semicolon" in reason.lower()


def test_policy_blocks_blocked_verbs() -> None:
    allowed, reason = is_allowed("reboot")
    assert not allowed
    assert "blocked" in reason.lower()


def test_policy_allows_getter() -> None:
    allowed, _ = is_allowed("status")
    assert allowed


def test_policy_allows_uppercase_and_whitespace() -> None:
    allowed, _ = is_allowed("  STATUS  ")
    assert allowed


def test_policy_allows_tabs_and_uppercase_setter() -> None:
    allowed, _ = is_allowed("FAN\t1")
    assert allowed


def test_policy_rejects_whitespace_only() -> None:
    allowed, reason = is_allowed("   \t ")
    assert not allowed
    assert "empty" in reason.lower()


def test_policy_requires_params_for_setter() -> None:
    allowed, reason = is_allowed("fan")
    assert not allowed
    assert "param" in reason.lower()


def test_policy_allows_setter_with_params() -> None:
    allowed, _ = is_allowed("fan 1")
    assert allowed


def test_policy_allows_dual_use_power_getter() -> None:
    allowed, _ = is_allowed("power")
    assert allowed


def test_policy_allows_dual_use_wave_getter() -> None:
    allowed, _ = is_allowed("wave")
    assert allowed


def test_policy_allows_dual_use_weld_param_getters() -> None:
    for cmd in ("headfre", "headwide", "feederoutspeed"):
        allowed, _ = is_allowed(cmd)
        assert allowed


def test_policy_allows_dual_use_weld_param_setters() -> None:
    for cmd in ("headfre 800", "headwide 80", "feederoutspeed 10"):
        allowed, _ = is_allowed(cmd)
        assert allowed
