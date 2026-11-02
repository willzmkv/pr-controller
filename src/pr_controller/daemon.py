"""pr-controller daemon: udev gamepad hotplug → profile → config writers → pr-builder.

Flow per gamepad (``ID_INPUT_JOYSTICK=1`` evdev node in the ``input``
subsystem):

    udev add    → vendor/product → resolve_profile() → RetroArch / ES-DE /
                  SDL writers → ``controller_added`` to pr-builder
    udev remove → ``controller_removed`` to pr-builder (configs are kept)

Pads already connected at startup are configured by a coldplug pass.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import socket
from typing import Optional

import pyudev

from pr_controller.config import (
    CONFIG_BASE,
    ESDE_INPUT_PATH,
    PR_BUILDER_SOCKET,
    RETROARCH_AUTOCONFIG_DIR,
    SDL_DB_PATH,
)
from pr_controller.device_db import GENERIC_DEVICE_NAME, is_known_device
from pr_controller.profile_manager import resolve_profile
from pr_controller.writers.esde import write_esde_config
from pr_controller.writers.native import write_sdl_gamecontrollerdb
from pr_controller.writers.retroarch import write_retroarch_autoconfig

log = logging.getLogger("pr-controller")

# Real indices are not discovered yet (see README "Known gaps"): unless a
# profile on disk provides button_indices the writers bind nothing and leave
# RetroArch/ES-DE/SDL on their built-in mappings.
_DEFAULT_BUTTON_INDICES: dict[str, object] = {}

_HEX_ID = re.compile(r"[0-9a-fA-F]{1,4}")


def _str_prop(device, key: str) -> Optional[str]:
    """String udev property or None (guards against non-str values)."""
    if device is None:
        return None
    value = device.get(key)
    return value if isinstance(value, str) and value else None


def _norm_id(value: Optional[str]) -> Optional[str]:
    if value is None or not _HEX_ID.fullmatch(value):
        return None
    return value.lower().zfill(4)


def device_ids(device) -> Optional[tuple[str, str]]:
    """(vendor_id, product_id) as 4-digit lowercase hex, or None.

    USB devices carry ID_VENDOR_ID/ID_MODEL_ID. Bluetooth (and other non-USB)
    pads do not, so fall back to ``PRODUCT=<bus>/<vendor>/<product>/<version>``
    on the event node's parent ``inputN`` device.
    """
    vendor = _norm_id(_str_prop(device, "ID_VENDOR_ID"))
    product = _norm_id(_str_prop(device, "ID_MODEL_ID"))
    if vendor and product:
        return vendor, product

    for dev in (device, getattr(device, "parent", None)):
        product_prop = _str_prop(dev, "PRODUCT")
        if not product_prop:
            continue
        parts = product_prop.split("/")
        if len(parts) >= 3:
            vendor, product = _norm_id(parts[1]), _norm_id(parts[2])
            if vendor and product:
                return vendor, product
    return None


def is_gamepad_device(device) -> bool:
    """True for a joystick's evdev node (not inputN, jsN, touchpads, sensors)."""
    node = getattr(device, "device_node", None)
    return (
        _str_prop(device, "ID_INPUT_JOYSTICK") == "1"
        and isinstance(node, str)
        and node.startswith("/dev/input/event")
    )


def _udev_name(device) -> Optional[str]:
    name = _str_prop(getattr(device, "parent", None), "NAME")
    if name:
        name = name.strip().strip('"').strip()
        if name:
            return name
    model = _str_prop(device, "ID_MODEL")
    return model.replace("_", " ").strip() if model else None


def handle_device_added(
    device,
    config_base: str,
    game_id: Optional[str],
    core_name: Optional[str],
    platform: Optional[str],
) -> Optional[dict]:
    """Process a udev 'add' event for a joystick/gamepad device.

    Returns the resolved profile, or None if the device has no usable IDs.
    """
    ids = device_ids(device)
    if ids is None:
        log.debug("Skipping device without vendor/product ID: %s", device.sys_path)
        return None
    vendor_id, product_id = ids

    profile = resolve_profile(
        vendor_id=vendor_id,
        product_id=product_id,
        game_id=game_id,
        core_name=core_name,
        platform=platform,
        config_base=config_base,
    )
    if profile.get("device_name") == GENERIC_DEVICE_NAME and not is_known_device(vendor_id, product_id):
        udev_name = _udev_name(device)
        if udev_name:
            profile["device_name"] = udev_name
    # In production the daemon populates button_indices from SDL before calling writers.
    if "button_indices" not in profile:
        profile["button_indices"] = dict(_DEFAULT_BUTTON_INDICES)

    writers = (
        ("RetroArch", write_retroarch_autoconfig, RETROARCH_AUTOCONFIG_DIR),
        ("ES-DE", write_esde_config, ESDE_INPUT_PATH),
        ("SDL", write_sdl_gamecontrollerdb, SDL_DB_PATH),
    )
    for label, writer, target in writers:
        try:
            written = writer(profile, target)
        except Exception:
            log.exception("%s config writer failed for %s", label, profile.get("device_name"))
            continue
        if written:
            log.info("Wrote %s config: %s", label, written)

    notify_pr_builder(
        socket_path=PR_BUILDER_SOCKET,
        event="controller_added",
        profile=profile,
    )
    log.info("Configured controller: %s (%s:%s, layout=%s)",
             profile.get("device_name"), vendor_id, product_id, profile.get("layout"))
    return profile


def handle_device_removed(device) -> None:
    """Process a udev 'remove' event: log and notify (written configs are kept)."""
    log.info("Controller removed: %s", device.sys_path)
    ids = device_ids(device)
    if ids is None:
        return
    node = getattr(device, "device_node", None)
    notify_pr_builder(
        socket_path=PR_BUILDER_SOCKET,
        event="controller_removed",
        profile={"vendor_id": ids[0], "product_id": ids[1],
                 "device_node": node if isinstance(node, str) else None},
    )


def notify_pr_builder(socket_path: str, event: str, profile: dict, timeout: float = 2.0) -> bool:
    """Send one newline-terminated JSON event to pr-builder's Unix socket.

    Best-effort: returns False (and logs) if pr-builder is absent, refuses,
    stalls past ``timeout`` or the payload cannot be encoded; never raises.
    """
    try:
        payload = (json.dumps({"type": event, "event": event, "profile": profile}) + "\n").encode()
    except (TypeError, ValueError) as exc:
        log.warning("Cannot encode %s notification: %s", event, exc)
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(socket_path)
            sock.sendall(payload)
    except OSError as exc:  # missing socket, refused, permission, timeout
        log.info("pr-builder not reachable at %s (%s); continuing", socket_path, exc)
        return False
    return True


def dispatch_event(device, config_base: str) -> None:
    """Route one udev event; errors are logged so the monitor loop survives."""
    if not is_gamepad_device(device):
        return
    try:
        if device.action == "add":
            handle_device_added(
                device,
                config_base=config_base,
                game_id=None,
                core_name=None,
                platform=None,
            )
        elif device.action == "remove":
            handle_device_removed(device)
    except Exception:
        log.exception("Failed to handle %s event for %s", device.action, device.sys_path)


def coldplug(context, config_base: str) -> None:
    """Configure gamepads that were already connected when the daemon started."""
    for device in context.list_devices(subsystem="input"):
        if not is_gamepad_device(device):
            continue
        try:
            handle_device_added(device, config_base=config_base,
                                game_id=None, core_name=None, platform=None)
        except Exception:
            log.exception("Failed to configure %s at startup", device.sys_path)


def _udev_monitor_loop(config_base: str) -> None:
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem="input")
    monitor.start()  # subscribe before coldplug so no hotplug falls in the gap
    coldplug(context, config_base)
    for device in iter(monitor.poll, None):
        dispatch_event(device, config_base)


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="pr-controller", description=__doc__.splitlines()[0])
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    log.info("pr-controller daemon starting. config_base=%s", CONFIG_BASE)
    log.info("outputs: retroarch=%s esde=%s sdl=%s pr-builder=%s",
             RETROARCH_AUTOCONFIG_DIR, ESDE_INPUT_PATH, SDL_DB_PATH, PR_BUILDER_SOCKET)
    try:
        _udev_monitor_loop(CONFIG_BASE)
    except KeyboardInterrupt:
        log.info("pr-controller stopping")


if __name__ == "__main__":
    main()
