from __future__ import annotations

from typing import List, Optional, TypedDict


class ExtraKV(TypedDict):
    key: str
    value: str


class ProcessParsed(TypedDict, total=False):
    power: int | float
    pwm_fre: int
    pwm_duty: int
    mode: int
    head_mode: int
    head_fre: int
    head_width: int
    pulse_on: int
    pulse_off: int
    gas_early: int
    gas_delay: int
    pow_rise: int
    pow_fall: int
    pow_early: int
    pow_delay: int
    power_on: int
    power_off: int
    index: int
    feeder_mode: int
    feeder_out_speed: int
    feeder_out_len: int
    feeder_in_speed: int
    feeder_in_len: int
    feeder_cycle: int
    feeder_smoothness: int
    feeder_out_delay: int
    feeder_in_delay: int
    extras: List[ExtraKV]


def _parse_num(value: str) -> Optional[int | float]:
    v = value.strip()
    if not v:
        return None
    try:
        if "." in v:
            f = float(v)
            return int(f) if f.is_integer() else f
        return int(v)
    except ValueError:
        return None


def _split_kv(line: str) -> Optional[ExtraKV]:
    if ":" not in line:
        return None
    key, value = line.split(":", 1)
    return {"key": key.strip(), "value": value.strip()}


def parse_process_block(text: str) -> ProcessParsed:
    text = text.replace("\r", "")
    lines = [l.strip() for l in text.splitlines() if l.strip() and l.strip() != "msh >"]

    out: ProcessParsed = {}
    extras: List[ExtraKV] = []

    def set_int(field: str, value: str) -> None:
        num = _parse_num(value)
        if num is None:
            return
        if isinstance(num, float) and not num.is_integer():
            return
        out[field] = int(num)

    def set_num(field: str, value: str) -> None:
        num = _parse_num(value)
        if num is None:
            return
        out[field] = num

    for raw in lines:
        s = raw.strip()
        lower = s.lower()

        if lower.startswith("power:") and "," in s:
            for part in s.split(","):
                if ":" not in part:
                    continue
                k, v = part.split(":", 1)
                k = k.strip().lower()
                if k == "power":
                    set_num("power", v)
                elif k == "fre":
                    set_int("pwm_fre", v)
                elif k == "duty":
                    set_int("pwm_duty", v)
                elif k == "mode":
                    set_int("mode", v)
            continue

        if lower.startswith("head mode:"):
            _, rest = s.split(":", 1)
            parts = [p.strip() for p in rest.split(",") if p.strip()]
            if parts:
                set_int("head_mode", parts[0])
                for part in parts[1:]:
                    if ":" not in part:
                        continue
                    k, v = part.split(":", 1)
                    k = k.strip().lower()
                    if k == "fre":
                        set_int("head_fre", v)
                    elif k == "width":
                        set_int("head_width", v)
            continue

        if lower.startswith("pulse tick"):
            rest = s[len("pulse tick") :].strip()
            if rest.startswith(":"):
                rest = rest[1:].strip()
            for part in rest.split(","):
                if ":" not in part:
                    continue
                k, v = part.split(":", 1)
                k = k.strip().lower()
                if k == "on":
                    set_int("pulse_on", v)
                elif k == "off":
                    set_int("pulse_off", v)
            continue

        if lower.startswith("gas tick"):
            rest = s[len("gas tick") :].strip()
            if rest.startswith(":"):
                rest = rest[1:].strip()
            for part in rest.split(","):
                if ":" not in part:
                    continue
                k, v = part.split(":", 1)
                k = k.strip().lower()
                if k == "early":
                    set_int("gas_early", v)
                elif k == "delay":
                    set_int("gas_delay", v)
            continue

        if lower.startswith("power tick"):
            rest = s[len("power tick") :].strip()
            if rest.startswith(":"):
                rest = rest[1:].strip()
            for part in rest.split(","):
                if ":" not in part:
                    continue
                k, v = part.split(":", 1)
                k = k.strip().lower()
                if k == "rise":
                    set_int("pow_rise", v)
                elif k == "fall":
                    set_int("pow_fall", v)
                elif k == "early":
                    set_int("pow_early", v)
                elif k == "delay":
                    set_int("pow_delay", v)
            continue

        if lower.startswith("power on"):
            for part in s.split(","):
                if ":" not in part:
                    continue
                k, v = part.split(":", 1)
                k = k.strip().lower()
                if k == "power on":
                    set_int("power_on", v)
                elif k == "power off":
                    set_int("power_off", v)
            continue

        if lower.startswith("process index:"):
            _, v = s.split(":", 1)
            set_int("index", v)
            continue

        if lower.startswith("feeder_mode:"):
            expect_out_len = False
            expect_in_len = False
            for part in s.split(","):
                if ":" not in part:
                    continue
                k, v = part.split(":", 1)
                k = k.strip().lower()
                if k == "feeder_mode":
                    set_int("feeder_mode", v)
                elif k == "out_speed":
                    set_int("feeder_out_speed", v)
                    expect_out_len = True
                    expect_in_len = False
                elif k == "in_speed":
                    set_int("feeder_in_speed", v)
                    expect_in_len = True
                    expect_out_len = False
                elif k == "len":
                    if expect_out_len:
                        set_int("feeder_out_len", v)
                        expect_out_len = False
                    elif expect_in_len:
                        set_int("feeder_in_len", v)
                        expect_in_len = False
            continue

        if lower.startswith("feeder_cycle:") or lower.startswith("smoothness:"):
            for part in s.split(","):
                if ":" not in part:
                    continue
                k, v = part.split(":", 1)
                k = k.strip().lower()
                if k == "feeder_cycle":
                    set_int("feeder_cycle", v)
                elif k == "smoothness":
                    set_int("feeder_smoothness", v)
                elif k == "out_delay":
                    set_int("feeder_out_delay", v)
                elif k == "in_delay":
                    set_int("feeder_in_delay", v)
                elif k == "out_len":
                    set_int("feeder_out_len", v)
                elif k == "in_len":
                    set_int("feeder_in_len", v)
            continue

        kv = _split_kv(s)
        if kv:
            extras.append(kv)

    if extras:
        out["extras"] = extras

    return out
