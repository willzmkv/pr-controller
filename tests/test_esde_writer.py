import xml.etree.ElementTree as ET
from pr_controller.writers.esde import write_esde_config


_PS4_PROFILE = {
    "device_name": "Sony DualShock 4",
    "vendor_id": "054c",
    "product_id": "09cc",
    "layout": "playstation",
    "mappings": {
        "a": "cross", "b": "circle", "x": "square", "y": "triangle",
        "start": "options", "select": "share",
        "l1": "l1", "r1": "r1",
        "up": "dpad_up", "down": "dpad_down",
        "left": "dpad_left", "right": "dpad_right",
    },
    "button_indices": {
        "cross": 0, "circle": 1, "square": 2, "triangle": 3,
        "share": 8, "options": 9,
        "l1": 4, "r1": 5,
        "dpad_up": "h0up", "dpad_down": "h0down",
        "dpad_left": "h0left", "dpad_right": "h0right",
    },
}


def test_write_creates_file(tmp_path):
    out = tmp_path / "es_input.cfg"
    write_esde_config(_PS4_PROFILE, str(out))
    assert out.exists()


def test_output_is_valid_xml(tmp_path):
    out = tmp_path / "es_input.cfg"
    write_esde_config(_PS4_PROFILE, str(out))
    tree = ET.parse(str(out))
    root = tree.getroot()
    assert root.tag == "inputList"


def test_input_config_element_present(tmp_path):
    out = tmp_path / "es_input.cfg"
    write_esde_config(_PS4_PROFILE, str(out))
    tree = ET.parse(str(out))
    root = tree.getroot()
    configs = root.findall("inputConfig")
    assert len(configs) == 1
    cfg = configs[0]
    assert cfg.attrib["deviceName"] == "Sony DualShock 4"
    assert cfg.attrib["deviceGUID"].startswith("03000000")


def test_a_button_mapped_to_a_action(tmp_path):
    out = tmp_path / "es_input.cfg"
    write_esde_config(_PS4_PROFILE, str(out))
    tree = ET.parse(str(out))
    root = tree.getroot()
    inputs = root.find("inputConfig").findall("input")
    a_inputs = [i for i in inputs if i.attrib["name"] == "a"]
    assert len(a_inputs) == 1
    assert a_inputs[0].attrib["type"] == "button"
    assert a_inputs[0].attrib["id"] == "0"


def test_dpad_up_mapped_as_hat(tmp_path):
    out = tmp_path / "es_input.cfg"
    write_esde_config(_PS4_PROFILE, str(out))
    tree = ET.parse(str(out))
    root = tree.getroot()
    inputs = root.find("inputConfig").findall("input")
    up_inputs = [i for i in inputs if i.attrib["name"] == "up"]
    assert len(up_inputs) == 1
    assert up_inputs[0].attrib["type"] == "hat"
    assert up_inputs[0].attrib["id"] == "0"
    assert up_inputs[0].attrib["value"] == "1"  # SDL hat up = 1


def test_start_and_select_present(tmp_path):
    out = tmp_path / "es_input.cfg"
    write_esde_config(_PS4_PROFILE, str(out))
    tree = ET.parse(str(out))
    root = tree.getroot()
    inputs = root.find("inputConfig").findall("input")
    names = {i.attrib["name"] for i in inputs}
    assert "start" in names
    assert "select" in names


# --- additions beyond the plan ----------------------------------------------

_EXISTING = """<?xml version="1.0"?>
<inputList>
  <inputAction type="onfinish">
    <command>/usr/bin/true</command>
  </inputAction>
  <inputConfig type="keyboard" deviceName="Keyboard" deviceGUID="-1">
    <input name="a" type="key" id="13" value="1" />
  </inputConfig>
  <inputConfig type="controller" deviceName="Sony DualShock 4" deviceGUID="030000004c050000cc09000000000000">
    <input name="a" type="button" id="0" value="1" />
  </inputConfig>
  <inputConfig type="joystick" deviceName="Other Pad" deviceGUID="03000000ffff00000100000000000000">
    <input name="a" type="button" id="7" value="1" />
  </inputConfig>
</inputList>
"""


def _configs(path):
    return ET.parse(str(path)).getroot().findall("inputConfig")


def test_guid_uses_sdl_little_endian_byte_order(tmp_path):
    out = tmp_path / "es_input.xml"
    write_esde_config(_PS4_PROFILE, str(out))
    # Real SDL GUID of a USB DualShock 4 is 030000004c050000cc090000xxxx0000
    assert _configs(out)[0].attrib["deviceGUID"] == "030000004c050000cc09000000000000"


def test_other_devices_and_es_de_entries_are_preserved(tmp_path):
    out = tmp_path / "es_input.xml"
    out.write_text(_EXISTING)
    write_esde_config(_PS4_PROFILE, str(out))
    root = ET.parse(str(out)).getroot()
    assert root.find("inputAction/command").text == "/usr/bin/true"
    kinds = [(c.attrib["type"], c.attrib["deviceName"]) for c in root.findall("inputConfig")]
    assert ("keyboard", "Keyboard") in kinds
    assert ("controller", "Sony DualShock 4") in kinds   # ES-DE's own entry untouched
    assert ("joystick", "Other Pad") in kinds
    assert ("joystick", "Sony DualShock 4") in kinds


def test_rewriting_same_device_replaces_its_entry(tmp_path):
    out = tmp_path / "es_input.xml"
    out.write_text(_EXISTING)
    write_esde_config(_PS4_PROFILE, str(out))
    write_esde_config(_PS4_PROFILE, str(out))
    ours = [c for c in _configs(out) if c.attrib["type"] == "joystick"
            and c.attrib["deviceName"] == "Sony DualShock 4"]
    assert len(ours) == 1
    assert len(_configs(out)) == 4


def test_no_bindings_leaves_file_untouched(tmp_path):
    out = tmp_path / "es_input.xml"
    assert write_esde_config(dict(_PS4_PROFILE, button_indices={}), str(out)) is None
    assert not out.exists()
    out.write_text(_EXISTING)
    write_esde_config(dict(_PS4_PROFILE, button_indices={}), str(out))
    assert out.read_text() == _EXISTING


def test_unparsable_existing_file_is_not_clobbered(tmp_path):
    out = tmp_path / "es_input.xml"
    out.write_text("<inputList><broken")
    assert write_esde_config(_PS4_PROFILE, str(out)) is None
    assert out.read_text() == "<inputList><broken"
