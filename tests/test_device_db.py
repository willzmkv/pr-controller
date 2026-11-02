from pr_controller.device_db import lookup_device, LAYOUT_PLAYSTATION, LAYOUT_XBOX, LAYOUT_SNES


def test_ps4_dualshock4_returns_playstation_layout():
    result = lookup_device(vendor_id="054c", product_id="09cc")
    assert result["layout"] == LAYOUT_PLAYSTATION
    assert result["device_name"] == "Sony DualShock 4"


def test_ps5_dualsense_returns_playstation_layout():
    result = lookup_device(vendor_id="054c", product_id="0ce6")
    assert result["layout"] == LAYOUT_PLAYSTATION
    assert result["device_name"] == "Sony DualSense"


def test_xbox_one_controller_returns_xbox_layout():
    result = lookup_device(vendor_id="045e", product_id="02ea")
    assert result["layout"] == LAYOUT_XBOX
    assert result["device_name"] == "Xbox One Controller"


def test_xbox_series_controller_returns_xbox_layout():
    result = lookup_device(vendor_id="045e", product_id="0b12")
    assert result["layout"] == LAYOUT_XBOX
    assert result["device_name"] == "Xbox Series Controller"


def test_unknown_vendor_returns_snes_layout():
    result = lookup_device(vendor_id="ffff", product_id="ffff")
    assert result["layout"] == LAYOUT_SNES
    assert result["device_name"] == "Generic Controller"


def test_lookup_is_case_insensitive():
    lower = lookup_device(vendor_id="054c", product_id="09cc")
    upper = lookup_device(vendor_id="054C", product_id="09CC")
    assert lower["layout"] == upper["layout"]


def test_ps4_dualshock4_has_default_mappings():
    result = lookup_device(vendor_id="054c", product_id="09cc")
    mappings = result["mappings"]
    assert mappings["a"] == "cross"
    assert mappings["b"] == "circle"
    assert mappings["x"] == "square"
    assert mappings["y"] == "triangle"
    assert mappings["start"] == "options"
    assert mappings["select"] == "share"
    assert mappings["up"] == "dpad_up"


def test_xbox_controller_has_xbox_button_names():
    result = lookup_device(vendor_id="045e", product_id="02ea")
    mappings = result["mappings"]
    assert mappings["a"] == "a"
    assert mappings["b"] == "b"
    assert mappings["x"] == "x"
    assert mappings["y"] == "y"
    assert mappings["start"] == "start"
    assert mappings["select"] == "back"


def test_generic_controller_has_snes_button_names():
    result = lookup_device(vendor_id="ffff", product_id="ffff")
    mappings = result["mappings"]
    assert mappings["a"] == "b_snes"
    assert mappings["b"] == "a_snes"
    assert mappings["x"] == "y_snes"
    assert mappings["y"] == "x_snes"


def test_mutating_result_does_not_change_builtin_table():
    first = lookup_device(vendor_id="054c", product_id="09cc")
    first["mappings"]["a"] = "hacked"
    second = lookup_device(vendor_id="054c", product_id="05c4")  # shares the PS table
    assert second["mappings"]["a"] == "cross"


def test_is_known_device():
    from pr_controller.device_db import is_known_device

    assert is_known_device("054C", "09CC")
    assert not is_known_device("ffff", "ffff")
