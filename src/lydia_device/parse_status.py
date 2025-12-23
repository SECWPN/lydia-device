import re
from typing import Any, Dict, List, Optional, TypedDict

# ---------- Typed schema for frontend ----------


class NtcReading(TypedDict):
    c: float
    adc: int


class PowerOut(TypedDict):
    pct: float
    w: int
    dac: int
    state: str


class PowerParam(TypedDict):
    power: float
    pwm_fre: int
    pwm_duty: int


class PowerDrive(TypedDict):
    v: float
    a: float


class EnergyState(TypedDict):
    state: int
    j: int
    dac: int


class PilotState(TypedDict):
    ma: float
    adc: int
    dac: int
    onoff: str
    mode: int


class PdVoltage(TypedDict):
    mv: float
    adc: int


class EnvSummary(TypedDict):
    temp_c: float
    pres_kpa: float
    dew: float


class StatusParsed(TypedDict, total=False):
    power_on_time: str
    rtc_time: str
    work_mode: str
    work_state: str
    laser_state: str
    pulse_on: int
    pulse_off: int
    wave_state: int
    io_flags: Dict[str, int]
    power_out: PowerOut
    power_param: PowerParam
    power_drive: PowerDrive
    drive_volt: List[float]
    drive_current: List[float]
    energy: EnergyState
    pilot: PilotState
    pd: PdVoltage
    ntc: List[NtcReading]  # length up to 8
    pressure: Dict[str, float | int]
    air_hr: Dict[str, float | int]
    air_t: Dict[str, float | int]
    env: EnvSummary
    warning: Dict[str, str]
    error: Dict[str, str]
    lock: Dict[str, str]
    tem: int


# ---------- Parser helpers ----------

_kv = lambda k, v: (k, v.strip())


def _find1(pat: str, text: str) -> Optional[str]:
    m = re.search(pat, text, flags=re.MULTILINE)
    return m.group(1) if m else None


def _find_float_list(pat: str, text: str) -> Optional[List[float]]:
    m = re.search(pat, text, flags=re.MULTILINE)
    if not m:
        return None
    nums = [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", m.group(1))]
    return nums


def _parse_ntc_line(line: str) -> List[NtcReading]:
    # e.g. "NTC1~4: 22.4C,ADC(2162), 0.0C,ADC(4091), ..."
    # extract pairs like "<temp>C,ADC(<adc>)"
    out: List[NtcReading] = []
    for t, adc in re.findall(r"([-+]?\d+(?:\.\d+)?)C,ADC\((\d+)\)", line):
        out.append({"c": float(t), "adc": int(adc)})
    return out


def parse_status_block(text: str) -> StatusParsed:
    text = text.replace("\r", "")
    out: StatusParsed = {}

    # times
    v = _find1(r"^Power-ON time:\s*(.+)$", text)
    if v:
        out["power_on_time"] = v
    v = _find1(r"^RTC time:\s*(.+)$", text)
    if v:
        out["rtc_time"] = v

    # simple fields
    for pat, key in [
        (r"^Work Mode:\s*(.+)$", "work_mode"),
        (r"^Work State:\s*(.+)$", "work_state"),
        (r"^laser State:\s*(.+)$", "laser_state"),
    ]:
        v = _find1(pat, text)
        if v:
            out[key] = v

    for pat, key in [
        (r"^pulse_on:\s*(\d+)\s*(?:[A-Za-z]+)?\s*$", "pulse_on"),
        (r"^pulse_off:\s*(\d+)\s*(?:[A-Za-z]+)?\s*$", "pulse_off"),
        (r"^wave\s+state:\s*(\d+)\s*$", "wave_state"),
    ]:
        v = _find1(pat, text)
        if v:
            out[key] = int(v)

    # IO flags
    v = _find1(r"^IO state:\s*(.+)$", text)
    if v:
        flags: Dict[str, int] = {}
        for name, val in re.findall(r"([A-Z0-9_]+)\((\d+)\)", v):
            flags[name] = int(val)
        out["io_flags"] = flags

    # Power Out
    m = re.search(
        r"^Power Out:\s*([0-9.]+)%.*?\(\s*([0-9]+)\s*w\),DAC\((\d+)\),state\((\w+)\)\s*$",
        text,
        flags=re.MULTILINE,
    )
    if m:
        out["power_out"] = {
            "pct": float(m.group(1)),
            "w": int(m.group(2)),
            "dac": int(m.group(3)),
            "state": m.group(4),
        }

    # Power Param: power(100.0),pwm_fre(1000),pwm_duty(100)
    m = re.search(
        r"^Power Param:\s*power\(([-+]?\d+(?:\.\d+)?)\),pwm_fre\((\d+)\),pwm_duty\((\d+)\)\s*$",
        text,
        flags=re.MULTILINE,
    )
    if m:
        out["power_param"] = {
            "power": float(m.group(1)),
            "pwm_fre": int(m.group(2)),
            "pwm_duty": int(m.group(3)),
        }

    # Power drive: 0.00 V, 0.00 A
    m = re.search(
        r"^Power drive:\s*([-+]?\d+(?:\.\d+)?)\s*V,\s*([-+]?\d+(?:\.\d+)?)\s*A\s*$",
        text,
        flags=re.MULTILINE,
    )
    if m:
        out["power_drive"] = {"v": float(m.group(1)), "a": float(m.group(2))}

    # Drive volt1~2 and current1~4
    volts = _find_float_list(r"^Drive volt1~2:\s*(.+)$", text)
    if volts is not None:
        out["drive_volt"] = volts[:2]
    currents = _find_float_list(r"^Drive current1~4:\s*(.+)$", text)
    if currents is not None:
        out["drive_current"] = currents[:4]

    # Energy: state(0),(0 J),DAC(255)
    m = re.search(
        r"^Energy:\s*state\((\d+)\),\((\d+)\s*J\),DAC\((\d+)\)\s*$",
        text,
        flags=re.MULTILINE,
    )
    if m:
        out["energy"] = {
            "state": int(m.group(1)),
            "j": int(m.group(2)),
            "dac": int(m.group(3)),
        }

    # Pilot State
    m = re.search(
        r"^Pilot State:\s*([0-9.]+)mA,ADC\((\d+)\),\s*DAC\((\d+)\),\s*\((\w+)\),\s*mode\((\d+)\)\s*$",
        text,
        flags=re.MULTILINE,
    )
    if m:
        out["pilot"] = {
            "ma": float(m.group(1)),
            "adc": int(m.group(2)),
            "dac": int(m.group(3)),
            "onoff": m.group(4),
            "mode": int(m.group(5)),
        }

    # PD Voltage
    m = re.search(
        r"^PD Voltage:\s*([0-9.]+)mV,ADC\((\d+)\)\s*$", text, flags=re.MULTILINE
    )
    if m:
        out["pd"] = {"mv": float(m.group(1)), "adc": int(m.group(2))}

    # NTC blocks
    ntc: List[NtcReading] = []
    for line_pat in [r"^NTC1~4:\s*(.+)$", r"^NTC5~8:\s*(.+)$"]:
        v = _find1(line_pat, text)
        if v:
            ntc.extend(_parse_ntc_line(v))
    if ntc:
        out["ntc"] = ntc  # index 0..7 correspond to NTC1..NTC8

    # Pressure / AirHR / AirT (value, ADC)
    m = re.search(r"^Pressure:\s*([0-9.]+),ADC\((\d+)\)\s*$", text, flags=re.MULTILINE)
    if m:
        out["pressure"] = {"value": float(m.group(1)), "adc": int(m.group(2))}
    m = re.search(r"^AirHR:\s*([0-9.]+)%?,ADC\((\d+)\)\s*$", text, flags=re.MULTILINE)
    if m:
        out["air_hr"] = {"value": float(m.group(1)), "adc": int(m.group(2))}
    m = re.search(r"^AirT:\s*([0-9.]+)C,ADC\((\d+)\)\s*$", text, flags=re.MULTILINE)
    if m:
        out["air_t"] = {"value_c": float(m.group(1)), "adc": int(m.group(2))}

    # Temp: 22.52 C  Pres: 384.00 KPa  / Dew: 0.00
    m = re.search(
        r"^Temp:\s*([0-9.]+)\s*C\s*Pres:\s*([0-9.]+)\s*KPa\s*$",
        text,
        flags=re.MULTILINE,
    )
    dew = _find1(r"^Dew:\s*([0-9.]+)\s*$", text)
    if m or dew:
        out["env"] = {
            "temp_c": float(m.group(1)) if m else float("nan"),
            "pres_kpa": float(m.group(2)) if m else float("nan"),
            "dew": float(dew) if dew else float("nan"),
        }

    # WARNING / ERROR / LOCK
    m = re.search(r"^WARNING\((0x[0-9A-Fa-f]+)\):\s*(.+)\s*$", text, flags=re.MULTILINE)
    if m:
        out["warning"] = {"mask": m.group(1), "text": m.group(2).strip()}
    m = re.search(r"^ERROR\((0x[0-9A-Fa-f]+)\):\s*(.+)\s*$", text, flags=re.MULTILINE)
    if m:
        out["error"] = {"mask": m.group(1), "text": m.group(2).strip()}
    m = re.search(r"^LOCK\((0x[0-9A-Fa-f]+)\):\s*(.*)\s*$", text, flags=re.MULTILINE)
    if m:
        out["lock"] = {"mask": m.group(1), "text": m.group(2).strip()}

    # TEM
    v = _find1(r"^TEM:(\d+)\s*$", text)
    if v:
        out["tem"] = int(v)

    return out
