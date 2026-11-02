from pr_controller.writers.native import write_sdl_gamecontrollerdb


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
    "button_indices": {
        "cross": 0, "circle": 1, "square": 2, "triangle": 3,
        "share": 8, "options": 9,
        "l1": 4, "r1": 5, "l2": 6, "r2": 7, "l3": 10, "r3": 11,
        "dpad_up": "h0up", "dpad_down": "h0down",
        "dpad_left": "h0left", "dpad_right": "h0right",
    },
}


def test_creates_file_if_missing(tmp_path):
    db = tmp_path / "gamecontrollerdb.txt"
    write_sdl_gamecontrollerdb(_PS4_PROFILE, str(db))
    assert db.exists()


def test_line_format(tmp_path):
    db = tmp_path / "gamecontrollerdb.txt"
    write_sdl_gamecontrollerdb(_PS4_PROFILE, str(db))
    lines = [l for l in db.read_text().splitlines() if l and not l.startswith("#")]
    assert len(lines) == 1
    parts = lines[0].split(",")
    assert parts[0].startswith("03000000")  # GUID
    assert parts[1] == "Sony DualShock 4"
    assert "platform:Linux" in lines[0]
    assert "a:b0," in lines[0]   # our 'a' (cross) → SDL 'a' → button 0


def test_existing_entry_is_replaced(tmp_path):
    db = tmp_path / "gamecontrollerdb.txt"
    write_sdl_gamecontrollerdb(_PS4_PROFILE, str(db))
    write_sdl_gamecontrollerdb(_PS4_PROFILE, str(db))
    lines = [l for l in db.read_text().splitlines() if l and not l.startswith("#")]
    assert len(lines) == 1  # not duplicated


# --- additions beyond the plan ----------------------------------------------

_GUID = "030000004c050000cc09000000000000"


def _entries(db):
    return [l for l in db.read_text().splitlines() if l and not l.startswith("#")]


def test_full_line_uses_sdl_guid_and_names(tmp_path):
    db = tmp_path / "db.txt"
    write_sdl_gamecontrollerdb(_PS4_PROFILE, str(db))
    assert _entries(db) == [
        f"{_GUID},Sony DualShock 4,a:b0,b:b1,x:b2,y:b3,start:b9,back:b8,"
        "leftshoulder:b4,rightshoulder:b5,lefttrigger:b6,righttrigger:b7,"
        "leftstick:b10,rightstick:b11,dpup:h0.1,dpdown:h0.4,dpleft:h0.8,dpright:h0.2,"
        "platform:Linux,"
    ]


def test_other_lines_and_comments_are_preserved(tmp_path):
    db = tmp_path / "db.txt"
    other = "03000000ffff00000100000000000000,Other Pad,a:b0,platform:Linux,"
    windows = f"{_GUID},PS4 Controller,a:b1,platform:Windows,"
    db.write_text(f"# header comment\n{other}\n{windows}\n")
    write_sdl_gamecontrollerdb(_PS4_PROFILE, str(db))
    text = db.read_text()
    assert text.startswith("# header comment\n")
    assert other in text
    assert windows in text  # only the Linux entry for this GUID is ours to replace
    assert len(_entries(db)) == 3


def test_fields_we_do_not_model_are_kept(tmp_path):
    # Sticks/guide/axis triggers are not part of our profile model; a rewrite
    # must not strip them from an existing full mapping for this GUID.
    db = tmp_path / "db.txt"
    db.write_text(f"{_GUID},PS4 Controller,a:b1,guide:b10,leftx:a0,lefty:a1,lefttrigger:a2,platform:Linux,\n")
    profile = dict(_PS4_PROFILE, button_indices={"cross": 0, "circle": 1})
    write_sdl_gamecontrollerdb(profile, str(db))
    [line] = _entries(db)
    fields = line.split(",")
    assert fields[1] == "Sony DualShock 4"
    assert "a:b0" in fields          # ours wins
    assert "b:b1" in fields
    for kept in ("guide:b10", "leftx:a0", "lefty:a1", "lefttrigger:a2"):
        assert kept in fields
    assert fields.count("platform:Linux") == 1
    assert line.endswith(",")


def test_comma_in_device_name_does_not_break_the_line(tmp_path):
    db = tmp_path / "db.txt"
    write_sdl_gamecontrollerdb(dict(_PS4_PROFILE, device_name="Pad, Deluxe"), str(db))
    assert _entries(db)[0].split(",")[1] == "Pad  Deluxe"


def test_no_bindings_writes_nothing(tmp_path):
    db = tmp_path / "db.txt"
    assert write_sdl_gamecontrollerdb(dict(_PS4_PROFILE, button_indices={}), str(db)) is None
    assert not db.exists()


def test_guid_helper_matches_known_sdl_guids():
    from pr_controller.writers._common import sdl_guid

    assert sdl_guid("054c", "09cc") == "030000004c050000cc09000000000000"
    assert sdl_guid("045E", "02EA") == "030000005e040000ea02000000000000"
