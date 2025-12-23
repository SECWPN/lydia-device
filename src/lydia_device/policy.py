from __future__ import annotations

from typing import Tuple

BLOCKED_VERBS = {
    "onkey",
    "offkey",
    "laser_en",
    "continuous",
    "pulse",
    "power",
    "laserdac",
    "drivedc",
    "drivedc",
    "pilot",
    "pilotdac",
    "piloti",
    "feederon",
    "feederoff",
    "feedermove",
    "outstart",
    "outstop",
    "instart",
    "instop",
    "writeio",
    "writeall",
    "reboot",
    "download",
    "chgboot",
    "setprocess",
    "applypro",
}

SAFE_GETTERS = {
    "status",
    "worktime",
    "warning",
    "error",
    "lock",
    "mode",
    "state",
    "substatus",
    "getall",
    "cur_pro",
    "feeder_pro",
    "maxpower",
    "temp",
    "pres",
    "pressure",
    "version",
    "help",
    "free",
    "ps",
    "list_device",
}

SAFE_SETTERS_REQUIRE_PARAMS = {
    "maxpower",
    "risetk",
    "falltk",
    "gaseatk",
    "gaslatk",
    "onwatk",
    "offwatk",
    "fan",
    "fanon",
    "fanduty",
    "fantemp",
    "intertimeout",
}


def normalize_verb(cmd: str) -> str:
    return (cmd.strip().split()[0] if cmd.strip() else "").lower()


def is_allowed(cmd: str) -> Tuple[bool, str]:
    c = cmd.strip()
    if not c:
        return False, "Empty command"
    if "\n" in c or "\r" in c:
        return False, "Multiline commands not allowed"
    if ";" in c:
        return False, "Semicolons not allowed"
    verb = normalize_verb(c)
    args = c.split()[1:]

    if verb in BLOCKED_VERBS:
        return False, f"Blocked verb: {verb}"

    if verb in SAFE_SETTERS_REQUIRE_PARAMS:
        if not args:
            return False, f"Missing parameters for setter: {verb}"
        return True, "Allowed setter-with-params"

    if verb in SAFE_GETTERS:
        return True, "Allowed getter"

    return False, f"Unknown/unaudited command: {verb}"
