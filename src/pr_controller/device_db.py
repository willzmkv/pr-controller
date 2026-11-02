"""Built-in vendor/product ID -> layout + default mappings table.

Mappings go from our generic, position-based names (``a`` = bottom face
button, ``b`` = right, ``x`` = left, ``y`` = top, as on an Xbox pad) to the
device's own button names; ``button_indices`` in a profile then maps those
device button names to hardware indices.
"""
from __future__ import annotations

import copy

LAYOUT_PLAYSTATION = "playstation"
LAYOUT_XBOX = "xbox"
LAYOUT_SNES = "snes"

GENERIC_DEVICE_NAME = "Generic Controller"

_PS_MAPPINGS = {
    "a": "cross", "b": "circle", "x": "square", "y": "triangle",
    "start": "options", "select": "share",
    "l1": "l1", "r1": "r1", "l2": "l2", "r2": "r2", "l3": "l3", "r3": "r3",
    "up": "dpad_up", "down": "dpad_down", "left": "dpad_left", "right": "dpad_right",
}

_XBOX_MAPPINGS = {
    "a": "a", "b": "b", "x": "x", "y": "y",
    "start": "start", "select": "back",
    "l1": "lb", "r1": "rb", "l2": "lt", "r2": "rt", "l3": "ls", "r3": "rs",
    "up": "dpad_up", "down": "dpad_down", "left": "dpad_left", "right": "dpad_right",
}

_SNES_MAPPINGS = {
    "a": "b_snes", "b": "a_snes", "x": "y_snes", "y": "x_snes",
    "start": "start", "select": "select",
    "l1": "l", "r1": "r", "l2": "zl", "r2": "zr", "l3": "l3", "r3": "r3",
    "up": "dpad_up", "down": "dpad_down", "left": "dpad_left", "right": "dpad_right",
}

# Keys are lowercase "vendor_id:product_id"
_KNOWN_DEVICES: dict[str, dict] = {
    # PlayStation
    "054c:09cc": {"device_name": "Sony DualShock 4", "layout": LAYOUT_PLAYSTATION, "mappings": _PS_MAPPINGS},
    "054c:05c4": {"device_name": "Sony DualShock 4 (rev1)", "layout": LAYOUT_PLAYSTATION, "mappings": _PS_MAPPINGS},
    "054c:0ce6": {"device_name": "Sony DualSense", "layout": LAYOUT_PLAYSTATION, "mappings": _PS_MAPPINGS},
    "054c:0df2": {"device_name": "Sony DualSense Edge", "layout": LAYOUT_PLAYSTATION, "mappings": _PS_MAPPINGS},
    # Xbox
    "045e:02ea": {"device_name": "Xbox One Controller", "layout": LAYOUT_XBOX, "mappings": _XBOX_MAPPINGS},
    "045e:0b12": {"device_name": "Xbox Series Controller", "layout": LAYOUT_XBOX, "mappings": _XBOX_MAPPINGS},
    "045e:028e": {"device_name": "Xbox 360 Controller", "layout": LAYOUT_XBOX, "mappings": _XBOX_MAPPINGS},
    "045e:02fd": {"device_name": "Xbox One S Controller", "layout": LAYOUT_XBOX, "mappings": _XBOX_MAPPINGS},
}

_GENERIC_DEVICE = {"device_name": GENERIC_DEVICE_NAME, "layout": LAYOUT_SNES, "mappings": _SNES_MAPPINGS}


def _key(vendor_id: str, product_id: str) -> str:
    return f"{vendor_id.lower()}:{product_id.lower()}"


def is_known_device(vendor_id: str, product_id: str) -> bool:
    """True if the IDs are in the built-in table (i.e. not the generic fallback)."""
    return _key(vendor_id, product_id) in _KNOWN_DEVICES


def lookup_device(vendor_id: str, product_id: str) -> dict:
    """Return device info dict for the given vendor/product IDs.

    Always returns a dict with keys: device_name, layout, mappings.
    Falls back to generic SNES layout for unknown devices. The result is a
    deep copy, so callers may mutate it freely.
    """
    return copy.deepcopy(_KNOWN_DEVICES.get(_key(vendor_id, product_id), _GENERIC_DEVICE))
