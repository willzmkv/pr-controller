from unittest.mock import MagicMock, patch, call
import pytest
from pr_controller.daemon import (
    handle_device_added,
    handle_device_removed,
    notify_pr_builder,
)


def _make_udev_device(vendor="054c", product="09cc", name="Sony DualShock 4"):
    dev = MagicMock()
    dev.get.side_effect = lambda key, default=None: {
        "ID_VENDOR_ID": vendor,
        "ID_MODEL_ID": product,
        "ID_MODEL": name,
    }.get(key, default)
    dev.sys_path = f"/sys/bus/hid/devices/{vendor}:{product}:0"
    return dev


def test_handle_device_added_writes_retroarch_config(tmp_path):
    dev = _make_udev_device()
    retroarch_dir = tmp_path / "retroarch" / "autoconfig"
    esde_path     = tmp_path / "es_input.cfg"
    sdl_db_path   = tmp_path / "gamecontrollerdb.txt"

    with patch("pr_controller.daemon.RETROARCH_AUTOCONFIG_DIR", str(retroarch_dir)), \
         patch("pr_controller.daemon.ESDE_INPUT_PATH", str(esde_path)), \
         patch("pr_controller.daemon.SDL_DB_PATH", str(sdl_db_path)), \
         patch("pr_controller.daemon.resolve_profile") as mock_resolve, \
         patch("pr_controller.daemon.write_retroarch_autoconfig") as mock_ra, \
         patch("pr_controller.daemon.write_esde_config") as mock_esde, \
         patch("pr_controller.daemon.write_sdl_gamecontrollerdb") as mock_sdl, \
         patch("pr_controller.daemon.notify_pr_builder") as mock_notify:

        mock_resolve.return_value = {
            "device_name": "Sony DualShock 4",
            "vendor_id": "054c",
            "product_id": "09cc",
            "layout": "playstation",
            "mappings": {},
            "button_indices": {},
        }
        handle_device_added(dev, config_base=str(tmp_path), game_id=None, core_name=None, platform=None)

    mock_ra.assert_called_once()
    mock_esde.assert_called_once()
    mock_sdl.assert_called_once()
    mock_notify.assert_called_once()


def test_handle_device_added_skips_non_joystick(tmp_path):
    dev = MagicMock()
    dev.get.return_value = None  # no vendor/product ID — not a gamepad
    with patch("pr_controller.daemon.write_retroarch_autoconfig") as mock_ra:
        handle_device_added(dev, config_base=str(tmp_path), game_id=None, core_name=None, platform=None)
    mock_ra.assert_not_called()


def test_notify_pr_builder_sends_json_over_socket(tmp_path):
    import socket, threading, json
    sock_path = str(tmp_path / "pr-builder.sock")

    received = []
    def server():
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(sock_path)
        srv.listen(1)
        srv.settimeout(2)
        conn, _ = srv.accept()
        data = conn.recv(4096)
        received.append(data)
        conn.close()
        srv.close()

    t = threading.Thread(target=server, daemon=True)
    t.start()
    import time; time.sleep(0.05)  # let server start

    notify_pr_builder(
        socket_path=sock_path,
        event="controller_added",
        profile={"device_name": "Sony DualShock 4", "layout": "playstation"},
    )
    t.join(timeout=2)

    assert received
    msg = json.loads(received[0].decode())
    assert msg["event"] == "controller_added"
    assert msg["profile"]["layout"] == "playstation"


# --- additions beyond the plan ----------------------------------------------

import json
import os
import socket
import threading

from pr_controller import daemon
from pr_controller.daemon import device_ids, is_gamepad_device, dispatch_event, coldplug


def _udev(props=None, node="/dev/input/event7", parent_props=None, action="add"):
    """Fake pyudev.Device: .get() reads props, .parent.get() reads parent_props."""
    props = dict(props or {})
    parent = MagicMock()
    parent.get.side_effect = lambda k, d=None: (parent_props or {}).get(k, d)
    dev = MagicMock()
    dev.get.side_effect = lambda k, d=None: props.get(k, d)
    dev.device_node = node
    dev.parent = parent
    dev.action = action
    dev.sys_path = "/sys/devices/virtual/input/input9/event7"
    return dev


_JOY_USB = {"ID_INPUT_JOYSTICK": "1", "ID_VENDOR_ID": "054c", "ID_MODEL_ID": "09cc"}


@pytest.fixture()
def outputs(tmp_path, monkeypatch):
    """Point every output at tmp_path and record pr-builder notifications."""
    paths = {
        "ra": tmp_path / "retroarch" / "autoconfig",
        "esde": tmp_path / "ES-DE" / "settings" / "es_input.xml",
        "sdl": tmp_path / "project-r" / "input" / "sdl_gamecontrollerdb.txt",
        "base": tmp_path / "project-r",
    }
    monkeypatch.setattr(daemon, "RETROARCH_AUTOCONFIG_DIR", str(paths["ra"]))
    monkeypatch.setattr(daemon, "ESDE_INPUT_PATH", str(paths["esde"]))
    monkeypatch.setattr(daemon, "SDL_DB_PATH", str(paths["sdl"]))
    sent = []
    monkeypatch.setattr(daemon, "notify_pr_builder",
                        lambda socket_path, event, profile: sent.append((socket_path, event, profile)))
    paths["sent"] = sent
    return paths


def test_device_ids_from_usb_properties():
    assert device_ids(_udev({"ID_VENDOR_ID": "054C", "ID_MODEL_ID": "09CC"})) == ("054c", "09cc")


def test_device_ids_bluetooth_falls_back_to_parent_product():
    # Bluetooth pads have no ID_VENDOR_ID/ID_MODEL_ID; the parent inputN
    # device carries PRODUCT=<bus>/<vendor>/<product>/<version> in hex.
    dev = _udev({"ID_INPUT_JOYSTICK": "1", "ID_BUS": "bluetooth"},
                parent_props={"PRODUCT": "5/54c/ce6/8100"})
    assert device_ids(dev) == ("054c", "0ce6")


@pytest.mark.parametrize("props, parent", [
    ({}, {}),
    ({"ID_VENDOR_ID": "zzzz", "ID_MODEL_ID": "09cc"}, {}),
    ({}, {"PRODUCT": "garbage"}),
])
def test_device_ids_invalid_returns_none(props, parent):
    assert device_ids(_udev(props, parent_props=parent)) is None


@pytest.mark.parametrize("props, node, expected", [
    (_JOY_USB, "/dev/input/event7", True),
    (_JOY_USB, "/dev/input/js0", False),            # legacy joydev node
    (_JOY_USB, None, False),                        # parent inputN, no node
    ({"ID_INPUT_TOUCHPAD": "1", "ID_VENDOR_ID": "054c"}, "/dev/input/event8", False),
    ({"ID_INPUT_ACCELEROMETER": "1"}, "/dev/input/event9", False),  # DS4 motion sensors
])
def test_is_gamepad_device(props, node, expected):
    assert is_gamepad_device(_udev(props, node=node)) is expected


def test_added_device_writes_all_configs_when_profile_has_indices(outputs):
    devices = outputs["base"] / "input" / "devices"
    devices.mkdir(parents=True)
    (devices / "054c_09cc.json").write_text(json.dumps(
        {"button_indices": {"cross": 0, "circle": 1, "dpad_up": "h0up"}}))

    profile = handle_device_added(_udev(_JOY_USB), config_base=str(outputs["base"]),
                                  game_id=None, core_name=None, platform=None)

    assert (outputs["ra"] / "Sony DualShock 4.cfg").exists()
    assert "deviceGUID=\"030000004c050000cc09000000000000\"" in outputs["esde"].read_text()
    assert outputs["sdl"].read_text().startswith("030000004c050000cc09000000000000,Sony DualShock 4,a:b0,b:b1,")
    [(sock, event, sent_profile)] = outputs["sent"]
    assert sock == daemon.PR_BUILDER_SOCKET
    assert event == "controller_added"
    assert sent_profile == profile
    assert (sent_profile["vendor_id"], sent_profile["layout"]) == ("054c", "playstation")


def test_added_device_without_indices_writes_nothing_but_notifies(outputs):
    handle_device_added(_udev(_JOY_USB), config_base=str(outputs["base"]),
                        game_id=None, core_name=None, platform=None)
    assert not outputs["ra"].exists()
    assert not outputs["esde"].exists()
    assert not outputs["sdl"].exists()
    assert [e for _, e, _ in outputs["sent"]] == ["controller_added"]


def test_unknown_device_is_named_from_udev(outputs):
    dev = _udev({"ID_INPUT_JOYSTICK": "1", "ID_VENDOR_ID": "2dc8", "ID_MODEL_ID": "6101",
                 "ID_MODEL": "8BitDo_SN30_Pro"},
                parent_props={"NAME": '"8BitDo SN30 Pro"'})
    profile = handle_device_added(dev, config_base=str(outputs["base"]),
                                  game_id=None, core_name=None, platform=None)
    assert profile["device_name"] == "8BitDo SN30 Pro"
    assert profile["layout"] == "snes"


def test_unknown_device_falls_back_to_id_model(outputs):
    dev = _udev({"ID_INPUT_JOYSTICK": "1", "ID_VENDOR_ID": "2dc8", "ID_MODEL_ID": "6101",
                 "ID_MODEL": "8BitDo_SN30_Pro"})
    profile = handle_device_added(dev, config_base=str(outputs["base"]),
                                  game_id=None, core_name=None, platform=None)
    assert profile["device_name"] == "8BitDo SN30 Pro"


def test_failing_writer_does_not_stop_the_others(outputs, monkeypatch):
    monkeypatch.setattr(daemon, "write_retroarch_autoconfig", MagicMock(side_effect=PermissionError("ro")))
    esde = MagicMock()
    monkeypatch.setattr(daemon, "write_esde_config", esde)
    handle_device_added(_udev(_JOY_USB), config_base=str(outputs["base"]),
                        game_id=None, core_name=None, platform=None)
    esde.assert_called_once()
    assert len(outputs["sent"]) == 1


def test_removed_device_notifies(outputs):
    handle_device_removed(_udev(_JOY_USB, action="remove"))
    [(_, event, profile)] = outputs["sent"]
    assert event == "controller_removed"
    assert (profile["vendor_id"], profile["product_id"]) == ("054c", "09cc")


def test_dispatch_routes_gamepads_and_ignores_the_rest(monkeypatch):
    added, removed = MagicMock(), MagicMock()
    monkeypatch.setattr(daemon, "handle_device_added", added)
    monkeypatch.setattr(daemon, "handle_device_removed", removed)

    dispatch_event(_udev(_JOY_USB, action="add"), config_base="/cfg")
    dispatch_event(_udev(_JOY_USB, action="remove"), config_base="/cfg")
    dispatch_event(_udev(_JOY_USB, action="change"), config_base="/cfg")
    dispatch_event(_udev(_JOY_USB, node="/dev/input/js0", action="add"), config_base="/cfg")
    dispatch_event(_udev({"ID_INPUT_MOUSE": "1"}, action="add"), config_base="/cfg")

    assert added.call_count == 1
    assert added.call_args.kwargs["config_base"] == "/cfg"
    assert removed.call_count == 1


def test_dispatch_survives_handler_errors(monkeypatch):
    monkeypatch.setattr(daemon, "handle_device_added", MagicMock(side_effect=RuntimeError("boom")))
    dispatch_event(_udev(_JOY_USB, action="add"), config_base="/cfg")  # must not raise


def test_coldplug_configures_already_connected_pads(monkeypatch):
    added = MagicMock()
    monkeypatch.setattr(daemon, "handle_device_added", added)
    context = MagicMock()
    context.list_devices.return_value = [
        _udev(_JOY_USB, action=None),
        _udev(_JOY_USB, node="/dev/input/js0", action=None),
        _udev({"ID_INPUT_KEYBOARD": "1"}, action=None),
    ]
    coldplug(context, config_base="/cfg")
    context.list_devices.assert_called_once_with(subsystem="input")
    assert added.call_count == 1


def test_monitor_loop_starts_monitor_before_coldplug_then_dispatches(monkeypatch):
    order = []
    monitor = MagicMock()
    monitor.start.side_effect = lambda: order.append("start")
    events = [_udev(_JOY_USB, action="add"), None]
    monitor.poll.side_effect = lambda: events.pop(0)
    fake_pyudev = MagicMock()
    fake_pyudev.Monitor.from_netlink.return_value = monitor
    monkeypatch.setattr(daemon, "pyudev", fake_pyudev)
    monkeypatch.setattr(daemon, "coldplug", lambda ctx, config_base: order.append("coldplug"))
    dispatched = []
    monkeypatch.setattr(daemon, "dispatch_event", lambda dev, config_base: dispatched.append(dev))

    daemon._udev_monitor_loop("/cfg")

    monitor.filter_by.assert_called_once_with(subsystem="input")
    assert order == ["start", "coldplug"]
    assert len(dispatched) == 1


def test_main_uses_project_r_config_dir_not_input_subdir(monkeypatch):
    # The plan's main() passed ~/.config/project-r/input, and resolve_profile
    # appends input/ itself, so no profile file was ever found.
    loop = MagicMock()
    monkeypatch.setattr(daemon, "_udev_monitor_loop", loop)
    daemon.main([])
    loop.assert_called_once_with(daemon.CONFIG_BASE)
    assert not daemon.CONFIG_BASE.rstrip("/").endswith("input")


def test_notify_message_is_newline_framed_with_type(sock_dir):
    # pr-builder's server reads one newline-terminated JSON line and keys
    # events on "type"; "event" is kept for the plan's contract.
    path = str(sock_dir / "b.sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    srv.listen(1)
    got = []

    def serve():
        conn, _ = srv.accept()
        with conn, conn.makefile("rb") as f:
            got.append(f.readline())

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    assert notify_pr_builder(path, "controller_added", {"layout": "xbox"}) is True
    t.join(2)
    srv.close()
    assert got[0].endswith(b"\n")
    assert json.loads(got[0]) == {"type": "controller_added", "event": "controller_added",
                                  "profile": {"layout": "xbox"}}


def test_notify_is_best_effort_when_pr_builder_is_absent(sock_dir):
    assert notify_pr_builder(str(sock_dir / "missing.sock"), "controller_added", {}) is False
    # Socket path exists but nobody listens
    stale = sock_dir / "stale.sock"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(stale))
    s.close()
    assert notify_pr_builder(str(stale), "controller_added", {}) is False


def test_notify_does_not_hang_on_a_stuck_listener(sock_dir):
    path = str(sock_dir / "stuck.sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    srv.listen(0)  # never accepts
    big = {"blob": "x" * (8 * 1024 * 1024)}  # larger than the socket buffer
    try:
        assert notify_pr_builder(path, "controller_added", big, timeout=0.5) is False
    finally:
        srv.close()
