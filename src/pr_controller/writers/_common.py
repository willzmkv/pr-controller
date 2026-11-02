"""Helpers shared by the config writers."""
from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Iterator

log = logging.getLogger(__name__)

_HAT_RE = re.compile(r"h(\d+)(up|down|left|right)")

# SDL hat bitmask values (SDL_HAT_UP/RIGHT/DOWN/LEFT)
HAT_VALUES = {"up": 1, "right": 2, "down": 4, "left": 8}


@dataclass(frozen=True)
class Binding:
    """One hardware input: a joystick button or a hat direction."""

    kind: str  # "button" | "hat"
    index: int  # button index, or hat index for kind == "hat"
    direction: str | None = None  # "up" / "down" / "left" / "right" for hats

    @property
    def hat_value(self) -> int:
        return HAT_VALUES[self.direction] if self.direction else 0


def parse_binding(value: object) -> Binding | None:
    """Parse a ``button_indices`` value: an int (or digit string) or ``hNdir``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Binding("button", value) if value >= 0 else None
    if isinstance(value, str):
        s = value.strip().lower()
        if s.isdigit():
            return Binding("button", int(s))
        m = _HAT_RE.fullmatch(s)
        if m:
            return Binding("hat", int(m.group(1)), m.group(2))
    return None


def iter_bindings(profile: dict, name_map: dict[str, str]) -> Iterator[tuple[str, Binding]]:
    """Yield ``(target_name, Binding)`` for every generic name in ``name_map``.

    generic name --mappings--> device button --button_indices--> hardware input.
    Unmapped names (missing or null) and unknown indices are skipped.
    """
    mappings = profile.get("mappings") or {}
    indices = profile.get("button_indices") or {}
    for generic_name, target in name_map.items():
        device_button = mappings.get(generic_name)
        if device_button is None:
            continue
        raw = indices.get(device_button)
        if raw is None:
            continue
        binding = parse_binding(raw)
        if binding is None:
            log.warning("Unsupported index %r for %s/%s — skipped", raw, generic_name, device_button)
            continue
        yield target, binding


def _le16(hex_id: str) -> str:
    """'054c' -> '4c05' (16-bit little-endian, as SDL lays out GUID bytes)."""
    value = int(hex_id, 16) & 0xFFFF
    return f"{value & 0xFF:02x}{value >> 8:02x}"


def sdl_guid(vendor_id: str, product_id: str) -> str:
    """SDL joystick GUID for a USB (bus 0x03) device, CRC and version zeroed.

    Layout (16 bytes, little-endian fields): bus, crc, vendor, 0, product, 0,
    version, 0. SDL2 >= 2.26 and SDL3 fall back to a version-less match, so
    a zero version matches every firmware revision of the device.
    """
    return f"03000000{_le16(vendor_id)}0000{_le16(product_id)}000000000000"


def atomic_write_text(path: str, text: str) -> None:
    """Write ``text`` to ``path`` via a temp file + rename in the same dir.

    Consumers (RetroArch, ES-DE, SDL games) read these files on hotplug, so
    they must never see a half-written file.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
