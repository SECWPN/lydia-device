import math
import pytest

from lydia_device.parse_status import parse_status_block


def test_parse_status_block_smoke() -> None:
    text = """Power-ON time: 01:02:03
RTC time: 2024-01-01 00:00:00
Work Mode: AUTO
Work State: IDLE
laser State: OFF
pulse_on:10
pulse_off:20
wave state:3
IO state: DOOR(1) COVER(0)
Power Out: 12.5% ( 34 w),DAC(255),state(ON)
Power Param: power(100.0),pwm_fre(1000),pwm_duty(100)
Power drive: 5.00 V, 1.25 A
Drive volt1~2: 10.0 20.0
Drive current1~4: 1.0 2.0 3.0 4.0
Energy: state(1),(10 J),DAC(255)
Pilot State: 12.3mA,ADC(123), DAC(45), (ON), mode(2)
PD Voltage: 23.4mV,ADC(99)
NTC1~4: 22.4C,ADC(2162), 23.0C,ADC(2100), 24.1C,ADC(2050), 25.2C,ADC(2000)
NTC5~8: 26.3C,ADC(1950), 27.4C,ADC(1900), 28.5C,ADC(1850), 29.6C,ADC(1800)
Pressure: 1.23,ADC(456)
AirHR: 55.0%,ADC(789)
AirT: 22.0C,ADC(111)
Temp: 22.52 C  Pres: 384.00 KPa
Dew: 0.00
WARNING(0x0001): OVERHEAT
ERROR(0x0000): NONE
LOCK(0x0000):
TEM:12
msh >
"""
    parsed = parse_status_block(text)

    assert parsed["work_mode"] == "AUTO"
    assert parsed["work_state"] == "IDLE"
    assert parsed["laser_state"] == "OFF"
    assert parsed["pulse_on"] == 10
    assert parsed["pulse_off"] == 20
    assert parsed["wave_state"] == 3
    assert parsed["io_flags"]["DOOR"] == 1
    assert parsed["power_out"]["w"] == 34
    assert parsed["power_param"]["pwm_fre"] == 1000
    assert parsed["drive_volt"] == [10.0, 20.0]
    assert parsed["drive_current"] == [1.0, 2.0, 3.0, 4.0]
    assert parsed["energy"]["j"] == 10
    assert parsed["pilot"]["mode"] == 2
    assert parsed["pd"]["adc"] == 99
    assert parsed["ntc"][0]["c"] == pytest.approx(22.4)
    assert parsed["pressure"]["value"] == pytest.approx(1.23)
    assert parsed["env"]["dew"] == pytest.approx(0.0)
    assert parsed["warning"]["mask"] == "0x0001"
    assert parsed["error"]["text"] == "NONE"
    assert parsed["tem"] == 12


def test_parse_status_missing_sections() -> None:
    text = """Work Mode: MANUAL
IO state: COVER(1)
TEMP: ignored
msh >
"""
    parsed = parse_status_block(text)

    assert parsed["work_mode"] == "MANUAL"
    assert parsed["io_flags"]["COVER"] == 1
    assert "warning" not in parsed
    assert "error" not in parsed
    assert "lock" not in parsed


def test_parse_status_missing_dew_line() -> None:
    text = """Temp: 25.0 C  Pres: 100.0 KPa
msh >
"""
    parsed = parse_status_block(text)

    assert "env" in parsed
    assert math.isnan(parsed["env"]["dew"])


def test_parse_status_unexpected_spacing_is_tolerated() -> None:
    text = """Work Mode:    AUTO
Power Out: 12.5% (34 w), DAC(255), state(ON)
msh >
"""
    parsed = parse_status_block(text)

    assert parsed["work_mode"] == "AUTO"
    assert "power_out" not in parsed


def test_parse_status_tolerates_cr_and_units() -> None:
    text = "pulse_on:150\r\npulse_off:150 ms\r\nwave state:0\r\nmsh >\r\n"
    parsed = parse_status_block(text)

    assert parsed["pulse_on"] == 150
    assert parsed["pulse_off"] == 150
    assert parsed["wave_state"] == 0
