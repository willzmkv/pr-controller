"""SDL ``gamecontrollerdb.txt`` writer for native SDL2/SDL3 ports.

SDL2 and SDL3 share this mapping format; games pick the file up through
``SDL_GAMECONTROLLERCONFIG_FILE`` (exported by the Project-R session).
"""
from __future__ import annotations

import logging
import os

from pr_controller.writers._common import atomic_write_text, iter_bindings, sdl_guid

log = logging.getLogger(__name__)

# Our generic name → SDL gamecontrollerdb button name
_SDL_NAME_MAP = {
    "a":      "a",
    "b":      "b",
    "x":      "x",
    "y":      "y",
    "start":  "start",
    "select": "back",
    "l1":     "leftshoulder",
    "r1":     "rightshoulder",
    "l2":     "lefttrigger",
    "r2":     "righttrigger",
    "l3":     "leftstick",
    "r3":     "rightstick",
    "up":     "dpup",
    "down":   "dpdown",
    "left":   "dpleft",
    "right":  "dpright",
}

_PLATFORM = "Linux"


def _make_guid(vendor_id: str, product_id: str) -> str:
    return sdl_guid(vendor_id, product_id)


def _parse_line(line: str) -> tuple[str, str, dict[str, str], str | None] | None:
    """Split a mapping line into (guid, name, fields, platform); None if not one."""
    parts = line.strip().split(",")
    if len(parts) < 2 or line.lstrip().startswith("#"):
        return None
    fields: dict[str, str] = {}
    platform = None
    for item in parts[2:]:
        key, sep, value = item.partition(":")
        if not sep:
            continue
        if key == "platform":
            platform = value
        else:
            fields[key] = value
    return parts[0], parts[1], fields, platform


def write_sdl_gamecontrollerdb(profile: dict, db_path: str) -> str | None:
    """Upsert this device's Linux entry in an SDL gamecontrollerdb.txt.

    An existing Linux line for the same GUID is replaced in place; fields we
    do not model (sticks, guide, axis triggers, ...) are carried over from
    it. Other lines and comments are kept untouched.

    Returns the path to the database file, or None if nothing could be bound
    (an empty entry would override SDL's built-in mapping for the device).
    """
    guid = _make_guid(profile["vendor_id"], profile["product_id"])
    name = profile["device_name"].replace(",", " ").replace("\n", " ")

    ours: dict[str, str] = {}
    for sdl_name, binding in iter_bindings(profile, _SDL_NAME_MAP):
        if binding.kind == "hat":
            ours[sdl_name] = f"h{binding.index}.{binding.hat_value}"
        else:
            ours[sdl_name] = f"b{binding.index}"
    if not ours:
        log.info("No bindable inputs for %s — SDL mapping DB left untouched", name)
        return None

    existing_lines: list[str] = []
    if os.path.exists(db_path):
        with open(db_path, "r", encoding="utf-8") as f:
            existing_lines = f.read().splitlines()

    result_lines: list[str] = []
    new_index: int | None = None
    fields: dict[str, str] = {}
    for line in existing_lines:
        parsed = _parse_line(line)
        if parsed and parsed[0] == guid and parsed[3] in (None, _PLATFORM):
            if new_index is None:
                fields = parsed[2]
                new_index = len(result_lines)
                result_lines.append("")  # placeholder, filled below
            continue  # drop duplicate entries for the same GUID
        result_lines.append(line)

    fields.update(ours)
    mapping = ",".join(f"{k}:{v}" for k, v in fields.items())
    new_line = f"{guid},{name},{mapping},platform:{_PLATFORM},"
    if new_index is None:
        result_lines.append(new_line)
    else:
        result_lines[new_index] = new_line

    atomic_write_text(db_path, "\n".join(result_lines) + "\n")
    return db_path
