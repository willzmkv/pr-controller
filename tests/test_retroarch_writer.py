import os
from pr_controller.writers.retroarch import write_retroarch_autoconfig


# Minimal profile as returned by profile_manager.resolve_profile()
_PS4_PROFILE = {
    "device_name": "Sony DualShock 4",
    "vendor_id": "054c",
    "product_id": "09cc",
    "layout": "playstation",
    "mappings": {
        "a": "cross", "b": "circle", "x": "square", "y": "triangle",
        "start": "options", "select": "share",
        "l1": "l1", "r1": "r1", "l2": "l2", "r2": "r2",
        "l3": "l3", "r3": "r3",
        "up": "dpad_up", "down": "dpad_down",
        "left": "dpad_left", "right": "dpad_right",
    },
    # SDL joystick button indices (provided by sdl_wrapper at runtime)
    "button_indices": {
        "cross": 0, "circle": 1, "square": 2, "triangle": 3,
        "share": 8, "options": 9,
        "l1": 4, "r1": 5, "l2": 6, "r2": 7,
        "l3": 10, "r3": 11,
        "dpad_up": "h0up", "dpad_down": "h0down",
        "dpad_left": "h0left", "dpad_right": "h0right",
    },
}


def test_write_creates_file(tmp_path):
    out = tmp_path / "Sony DualShock 4.cfg"
    write_retroarch_autoconfig(_PS4_PROFILE, str(tmp_path))
    assert out.exists()


def test_header_fields_present(tmp_path):
    write_retroarch_autoconfig(_PS4_PROFILE, str(tmp_path))
    content = (tmp_path / "Sony DualShock 4.cfg").read_text()
    assert 'input_driver = "udev"' in content
    assert 'input_device = "Sony DualShock 4"' in content
    assert 'input_vendor_id = "1356"' in content   # 0x054c = 1356 decimal
    assert 'input_product_id = "2508"' in content  # 0x09cc = 2508 decimal


def test_button_mappings_written(tmp_path):
    write_retroarch_autoconfig(_PS4_PROFILE, str(tmp_path))
    content = (tmp_path / "Sony DualShock 4.cfg").read_text()
    assert 'input_b_btn = "0"' in content          # a → cross → index 0
    # Plan fix: the plan asserted input_y_btn = "3", contradicting its own
    # key table (x → input_y). Our x is the left face button (square,
    # index 2) = RetroPad Y; our y is the top button (triangle, 3) = RetroPad X.
    assert 'input_y_btn = "2"' in content          # x → square → index 2
    assert 'input_x_btn = "3"' in content          # y → triangle → index 3
    assert 'input_select_btn = "8"' in content
    assert 'input_start_btn = "9"' in content


def test_dpad_hat_mappings_written(tmp_path):
    write_retroarch_autoconfig(_PS4_PROFILE, str(tmp_path))
    content = (tmp_path / "Sony DualShock 4.cfg").read_text()
    assert 'input_up_btn = "h0up"' in content
    assert 'input_down_btn = "h0down"' in content
    assert 'input_left_btn = "h0left"' in content
    assert 'input_right_btn = "h0right"' in content


def test_existing_file_is_overwritten(tmp_path):
    write_retroarch_autoconfig(_PS4_PROFILE, str(tmp_path))
    write_retroarch_autoconfig(_PS4_PROFILE, str(tmp_path))
    files = list(tmp_path.iterdir())
    assert len(files) == 1


# --- additions beyond the plan ----------------------------------------------


def test_returns_written_path(tmp_path):
    path = write_retroarch_autoconfig(_PS4_PROFILE, str(tmp_path))
    assert path == os.path.join(str(tmp_path), "Sony DualShock 4.cfg")


def test_no_bindings_writes_nothing(tmp_path):
    # An autoconfig with no binds would shadow RetroArch's own profile for
    # this vendor/product and leave the pad dead, so nothing is written.
    profile = dict(_PS4_PROFILE, button_indices={})
    assert write_retroarch_autoconfig(profile, str(tmp_path)) is None
    profile = {k: v for k, v in _PS4_PROFILE.items() if k != "button_indices"}
    assert write_retroarch_autoconfig(profile, str(tmp_path)) is None
    assert list(tmp_path.iterdir()) == []


def test_unmapped_and_invalid_indices_are_skipped(tmp_path):
    profile = dict(_PS4_PROFILE)
    profile["mappings"] = dict(_PS4_PROFILE["mappings"], start=None)
    profile["button_indices"] = dict(_PS4_PROFILE["button_indices"], l3="+a2", r3=True)
    write_retroarch_autoconfig(profile, str(tmp_path))
    content = (tmp_path / "Sony DualShock 4.cfg").read_text()
    assert "input_start_btn" not in content
    assert "input_l3_btn" not in content
    assert "input_r3_btn" not in content
    assert 'input_b_btn = "0"' in content


def test_device_name_is_sanitized_for_filename_and_value(tmp_path):
    profile = dict(_PS4_PROFILE, device_name='Weird/"Pad"')
    path = write_retroarch_autoconfig(profile, str(tmp_path))
    assert os.path.dirname(path) == str(tmp_path)
    assert os.path.basename(path) == "Weird_'Pad'.cfg"
    with open(path) as f:
        assert "input_device = \"Weird/'Pad'\"" in f.read()


def test_no_temp_files_left_behind(tmp_path):
    write_retroarch_autoconfig(_PS4_PROFILE, str(tmp_path / "autoconfig"))
    assert [p.name for p in (tmp_path / "autoconfig").iterdir()] == ["Sony DualShock 4.cfg"]
