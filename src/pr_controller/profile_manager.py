"""3-level controller profile resolution (most specific wins).

    1. game      <config_base>/input/games/{game_id}.json
    2. core      <config_base>/input/cores/{core_name}.json
       platform  <config_base>/input/platforms/{platform}.json  (core beats platform)
    3. device    <config_base>/input/devices/{vendor_id}_{product_id}.json
       built-in  device_db defaults underneath the device file

Each level is deep-merged over the one below it.
"""
from __future__ import annotations

import copy
import json
import logging
import os

from pr_controller.device_db import lookup_device

log = logging.getLogger(__name__)


def _load_json_or_none(path: str) -> dict | None:
    """Load a JSON object from path; None if missing, unreadable or not an object."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:  # ValueError covers JSON + UTF-8 errors
        log.warning("Ignoring unreadable profile %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        log.warning("Ignoring profile %s: top level is not a JSON object", path)
        return None
    return data


def _deep_merge(base: dict, override: dict) -> dict:
    """Return a new dict with override applied on top of base.

    Nested dicts are merged recursively; all other values are replaced.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _is_safe_name(name: str) -> bool:
    """Reject names that could leave the profile directory."""
    return bool(name) and "/" not in name and "\\" not in name and not name.startswith(".")


def _load_level(input_dir: str, level: str, name: str | None) -> dict | None:
    if not name:
        return None
    if not _is_safe_name(name):
        log.warning("Ignoring unsafe %s profile name %r", level, name)
        return None
    return _load_json_or_none(os.path.join(input_dir, level, f"{name}.json"))


def resolve_profile(
    vendor_id: str,
    product_id: str,
    game_id: str | None,
    core_name: str | None,
    platform: str | None,
    config_base: str,
) -> dict:
    """Resolve the effective controller profile for the given context.

    ``config_base`` is the Project-R config dir (``~/.config/project-r``);
    profiles live in its ``input/`` subdirectory.

    Returns a merged profile dict that always has ``device_name``,
    ``vendor_id``, ``product_id`` (lowercase hex), ``layout`` and ``mappings``.
    """
    vendor_id = vendor_id.lower()
    product_id = product_id.lower()
    input_dir = os.path.join(config_base, "input")

    # Level 3 — built-in defaults, then the per-device file on top
    profile = lookup_device(vendor_id=vendor_id, product_id=product_id)
    device_data = _load_level(input_dir, "devices", f"{vendor_id}_{product_id}")
    if device_data:
        profile = _deep_merge(profile, device_data)

    # Level 2 — platform, then core (core wins when both are present)
    for level, name in (("platforms", platform), ("cores", core_name)):
        data = _load_level(input_dir, level, name)
        if data:
            profile = _deep_merge(profile, data)

    # Level 1 — game (highest priority)
    game_data = _load_level(input_dir, "games", game_id)
    if game_data:
        profile = _deep_merge(profile, game_data)

    # Identity always reflects the physical device being configured.
    profile["vendor_id"] = vendor_id
    profile["product_id"] = product_id
    if not isinstance(profile.get("mappings"), dict):
        profile["mappings"] = lookup_device(vendor_id, product_id)["mappings"]
    return profile
