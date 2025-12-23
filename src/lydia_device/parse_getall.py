from __future__ import annotations

import re
from typing import Dict, TypedDict


class GetAllValue(TypedDict, total=False):
    raw: str
    value: int | float
    unit: str


GetAllParsed = Dict[str, GetAllValue]


_NUM_UNIT_RE = re.compile(r"^([-+]?\d+(?:\.\d+)?)(?:\s*([A-Za-z%/]+))?\s*$")


def parse_getall_block(text: str) -> GetAllParsed:
    text = text.replace("\r", "")
    out: GetAllParsed = {}

    for line in text.splitlines():
        s = line.strip()
        if not s or s == "msh >":
            continue
        if s.startswith("."):
            s = s[1:].strip()
        if ":" not in s:
            continue

        key, raw = s.split(":", 1)
        key = key.strip().lower()
        raw = raw.strip()

        entry: GetAllValue = {"raw": raw}
        m = _NUM_UNIT_RE.match(raw)
        if m:
            num = float(m.group(1))
            entry["value"] = int(num) if num.is_integer() else num
            if m.group(2):
                entry["unit"] = m.group(2)

        out[key] = entry

    return out
