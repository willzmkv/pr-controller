"""RetroArch joypad autoconfig writer (udev input driver)."""
from __future__ import annotations

import logging
import os

from pr_controller.writers._common import atomic_write_text, iter_bindings

log = logging.getLogger(__name__)

# Our generic name → RetroArch key prefix (without _btn suffix).
# RetroPad uses SNES naming: B = bottom, A = right, Y = left, X = top.
_RA_KEY_MAP = {
    "a":      "input_b",
    "b":      "input_a",
    "x":      "input_y",
    "y":      "input_x",
    "start":  "input_start",
    "select": "input_select",
    "l1":     "input_l",
    "r1":     "input_r",
    "l2":     "input_l2",
    "r2":     "input_r2",
    "l3":     "input_l3",
    "r3":     "input_r3",
    "up":     "input_up",
    "down":   "input_down",
    "left":   "input_left",
    "right":  "input_right",
}


def _cfg_value(text: str) -> str:
    # RetroArch config values are double-quoted with no escape syntax.
    return text.replace('"', "'").replace("\n", " ").replace("\r", " ")


def _file_name(device_name: str, vendor_id: str, product_id: str) -> str:
    name = device_name.replace("/", "_").replace("\0", "_").strip()
    if name in ("", ".", ".."):
        name = f"{vendor_id}_{product_id}"
    return f"{name}.cfg"


def write_retroarch_autoconfig(profile: dict, output_dir: str) -> str | None:
    """Write a RetroArch autoconfig file for the given profile.

    Args:
        profile: Merged profile dict from profile_manager.resolve_profile(),
                 plus a 'button_indices' key mapping device button names → indices.
        output_dir: Directory to write the .cfg file into.

    Returns:
        Path of the written file, or None if no input could be bound (an
        empty autoconfig would shadow RetroArch's own profile for the pad).
    """
    device_name = _cfg_value(profile["device_name"])
    vendor_dec  = str(int(profile["vendor_id"], 16))
    product_dec = str(int(profile["product_id"], 16))

    binds = []
    for ra_key, binding in iter_bindings(profile, _RA_KEY_MAP):
        if binding.kind == "hat":
            value = f"h{binding.index}{binding.direction}"
        else:
            value = str(binding.index)
        binds.append(f'{ra_key}_btn = "{value}"')

    if not binds:
        log.info("No bindable inputs for %s — RetroArch autoconfig left untouched", device_name)
        return None

    lines = [
        'input_driver = "udev"',
        f'input_device = "{device_name}"',
        f'input_vendor_id = "{vendor_dec}"',
        f'input_product_id = "{product_dec}"',
        *binds,
    ]
    out_path = os.path.join(
        output_dir, _file_name(device_name, profile["vendor_id"], profile["product_id"])
    )
    atomic_write_text(out_path, "\n".join(lines) + "\n")
    return out_path
