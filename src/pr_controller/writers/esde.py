"""ES-DE input config writer (``es_input.xml``).

Entries use the classic EmulationStation ``type="joystick"`` format from the
plan (raw joystick button/hat indices). The writer upserts only its own
entry — keyed by type + deviceGUID + deviceName — and keeps every other
element (keyboard, other pads, ES-DE's own ``type="controller"`` entries,
``inputAction`` blocks) intact.
"""
from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET

from pr_controller.writers._common import atomic_write_text, iter_bindings, sdl_guid

log = logging.getLogger(__name__)

_CONFIG_TYPE = "joystick"

# Our generic action names → ES-DE input action names
_ESDE_ACTIONS = {
    "a": "a", "b": "b", "x": "x", "y": "y",
    "start": "start", "select": "select",
    "l1": "pageup", "r1": "pagedown",
    "up": "up", "down": "down", "left": "left", "right": "right",
}


def _vendor_product_to_guid(vendor_id: str, product_id: str) -> str:
    """SDL GUID for the device (see writers._common.sdl_guid)."""
    return sdl_guid(vendor_id, product_id)


def _load_root(output_path: str) -> ET.Element | None:
    """Existing <inputList>, a fresh one if the file is absent, None if unusable."""
    if not os.path.exists(output_path):
        return ET.Element("inputList")
    try:
        root = ET.parse(output_path).getroot()
    except (ET.ParseError, OSError) as exc:
        log.warning("Not touching unparsable ES-DE input config %s: %s", output_path, exc)
        return None
    if root.tag != "inputList":
        log.warning("Not touching %s: root element is <%s>, not <inputList>", output_path, root.tag)
        return None
    return root


def write_esde_config(profile: dict, output_path: str) -> str | None:
    """Upsert this device's <inputConfig> in an ES-DE input config file.

    Args:
        profile: Merged profile dict (same shape as retroarch writer expects).
        output_path: Full path of the file (default ~/ES-DE/settings/es_input.xml).

    Returns:
        output_path, or None when nothing was written (no bindable inputs, or
        an existing file that cannot be parsed and so must not be clobbered).
    """
    inputs = []
    for action, binding in iter_bindings(profile, _ESDE_ACTIONS):
        if binding.kind == "hat":
            inputs.append({"name": action, "type": "hat",
                           "id": str(binding.index), "value": str(binding.hat_value)})
        else:
            inputs.append({"name": action, "type": "button",
                           "id": str(binding.index), "value": "1"})
    if not inputs:
        log.info("No bindable inputs for %s — ES-DE config left untouched", profile["device_name"])
        return None

    root = _load_root(output_path)
    if root is None:
        return None

    guid = _vendor_product_to_guid(profile["vendor_id"], profile["product_id"])
    for old in root.findall("inputConfig"):
        if (old.get("type") == _CONFIG_TYPE and old.get("deviceGUID") == guid
                and old.get("deviceName") == profile["device_name"]):
            root.remove(old)

    cfg_el = ET.SubElement(root, "inputConfig", {
        "type": _CONFIG_TYPE,
        "deviceName": profile["device_name"],
        "deviceGUID": guid,
    })
    for attrs in inputs:
        ET.SubElement(cfg_el, "input", attrs)

    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    atomic_write_text(output_path, '<?xml version="1.0"?>\n' + body + "\n")
    return output_path
