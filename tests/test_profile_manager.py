import json
import os
import pytest
from pr_controller.profile_manager import resolve_profile


@pytest.fixture()
def profile_dirs(tmp_path):
    """Create the 3-level config directories under tmp_path and return their paths."""
    games    = tmp_path / "input" / "games"
    cores    = tmp_path / "input" / "cores"
    platforms = tmp_path / "input" / "platforms"
    devices  = tmp_path / "input" / "devices"
    for d in (games, cores, platforms, devices):
        d.mkdir(parents=True)
    return {"games": games, "cores": cores, "platforms": platforms, "devices": devices, "base": tmp_path}


def _write_json(path, data):
    path.write_text(json.dumps(data))


def test_device_profile_used_when_no_game_or_core(profile_dirs):
    device_profile = {
        "device_name": "Sony DualShock 4",
        "vendor_id": "054c",
        "product_id": "09cc",
        "layout": "playstation",
        "mappings": {"a": "cross", "b": "circle"},
    }
    _write_json(profile_dirs["devices"] / "054c_09cc.json", device_profile)

    result = resolve_profile(
        vendor_id="054c", product_id="09cc",
        game_id=None, core_name=None, platform=None,
        config_base=str(profile_dirs["base"]),
    )
    assert result["layout"] == "playstation"
    assert result["mappings"]["a"] == "cross"


def test_game_profile_overrides_device_profile(profile_dirs):
    device_profile = {
        "layout": "playstation",
        "mappings": {"a": "cross", "b": "circle", "start": "options"},
    }
    game_profile = {
        "mappings": {"start": "touchpad"},  # override only start
    }
    _write_json(profile_dirs["devices"] / "054c_09cc.json", device_profile)
    _write_json(profile_dirs["games"] / "sm64-us.json", game_profile)

    result = resolve_profile(
        vendor_id="054c", product_id="09cc",
        game_id="sm64-us", core_name=None, platform=None,
        config_base=str(profile_dirs["base"]),
    )
    assert result["mappings"]["start"] == "touchpad"  # game wins
    assert result["mappings"]["a"] == "cross"          # device still present
    assert result["layout"] == "playstation"           # device layout preserved


def test_core_profile_overrides_device_but_game_wins(profile_dirs):
    device_profile = {"layout": "playstation", "mappings": {"a": "cross", "l2": "l2", "r2": "r2"}}
    core_profile   = {"mappings": {"l2": "zl_core"}}
    game_profile   = {"mappings": {"l2": "zl_game"}}
    _write_json(profile_dirs["devices"] / "054c_09cc.json", device_profile)
    _write_json(profile_dirs["cores"] / "mupen64plus_next.json", core_profile)
    _write_json(profile_dirs["games"] / "sm64-us.json", game_profile)

    result = resolve_profile(
        vendor_id="054c", product_id="09cc",
        game_id="sm64-us", core_name="mupen64plus_next", platform=None,
        config_base=str(profile_dirs["base"]),
    )
    assert result["mappings"]["l2"] == "zl_game"   # game beats core


def test_core_profile_beats_device_without_game(profile_dirs):
    device_profile = {"layout": "playstation", "mappings": {"a": "cross", "l2": "l2"}}
    core_profile   = {"mappings": {"l2": "zl_core"}}
    _write_json(profile_dirs["devices"] / "054c_09cc.json", device_profile)
    _write_json(profile_dirs["cores"] / "mupen64plus_next.json", core_profile)

    result = resolve_profile(
        vendor_id="054c", product_id="09cc",
        game_id=None, core_name="mupen64plus_next", platform=None,
        config_base=str(profile_dirs["base"]),
    )
    assert result["mappings"]["l2"] == "zl_core"


def test_platform_profile_at_level2(profile_dirs):
    device_profile   = {"layout": "playstation", "mappings": {"a": "cross", "start": "options"}}
    platform_profile = {"mappings": {"start": "steam_start"}}
    _write_json(profile_dirs["devices"] / "054c_09cc.json", device_profile)
    _write_json(profile_dirs["platforms"] / "steam.json", platform_profile)

    result = resolve_profile(
        vendor_id="054c", product_id="09cc",
        game_id=None, core_name=None, platform="steam",
        config_base=str(profile_dirs["base"]),
    )
    assert result["mappings"]["start"] == "steam_start"


def test_missing_device_profile_falls_back_to_device_db(profile_dirs):
    # No device JSON on disk — should fall back to device_db lookup
    result = resolve_profile(
        vendor_id="054c", product_id="09cc",
        game_id=None, core_name=None, platform=None,
        config_base=str(profile_dirs["base"]),
    )
    assert result["layout"] == "playstation"
    assert result["mappings"]["a"] == "cross"


def test_unknown_device_without_profile_returns_snes_layout(profile_dirs):
    result = resolve_profile(
        vendor_id="ffff", product_id="ffff",
        game_id=None, core_name=None, platform=None,
        config_base=str(profile_dirs["base"]),
    )
    assert result["layout"] == "snes"


# --- additions beyond the plan (bugs found while implementing) -------------


def _resolve(profile_dirs, **kw):
    args = dict(vendor_id="054c", product_id="09cc", game_id=None, core_name=None, platform=None)
    args.update(kw)
    return resolve_profile(config_base=str(profile_dirs["base"]), **args)


def test_resolved_profile_always_carries_device_identity(profile_dirs):
    # The writers need device_name/vendor_id/product_id; device_db does not
    # store the IDs and hand-written device files may omit them.
    _write_json(profile_dirs["devices"] / "054c_09cc.json", {"mappings": {"a": "circle"}})
    result = _resolve(profile_dirs, vendor_id="054C", product_id="09CC")
    assert result["vendor_id"] == "054c"
    assert result["product_id"] == "09cc"
    assert result["device_name"] == "Sony DualShock 4"
    assert result["layout"] == "playstation"


def test_fallback_profile_carries_device_identity(profile_dirs):
    result = _resolve(profile_dirs, vendor_id="ffff", product_id="0001")
    assert (result["vendor_id"], result["product_id"]) == ("ffff", "0001")
    assert result["device_name"] == "Generic Controller"


def test_partial_device_file_is_merged_over_builtin_defaults(profile_dirs):
    _write_json(profile_dirs["devices"] / "054c_09cc.json", {"mappings": {"a": "circle"}})
    result = _resolve(profile_dirs)
    assert result["mappings"]["a"] == "circle"     # file wins
    assert result["mappings"]["start"] == "options"  # built-in default kept


def test_core_beats_platform_when_both_given(profile_dirs):
    _write_json(profile_dirs["platforms"] / "steam.json", {"mappings": {"start": "plat", "select": "plat"}})
    _write_json(profile_dirs["cores"] / "mupen64plus_next.json", {"mappings": {"start": "core"}})
    result = _resolve(profile_dirs, core_name="mupen64plus_next", platform="steam")
    assert result["mappings"]["start"] == "core"
    assert result["mappings"]["select"] == "plat"


@pytest.mark.parametrize("content", ["{not json", "[1, 2, 3]", '"just a string"', ""])
def test_malformed_or_non_object_profile_is_ignored(profile_dirs, content):
    (profile_dirs["games"] / "broken.json").write_text(content)
    result = _resolve(profile_dirs, game_id="broken")
    assert result["mappings"]["a"] == "cross"


def test_profile_names_cannot_escape_their_directory(profile_dirs):
    # A game_id that walks into devices/ must not be loaded as a game profile.
    _write_json(profile_dirs["devices"] / "evil.json", {"mappings": {"a": "pwned"}})
    for bad in ("../devices/evil", "/abs/evil", ".hidden", "a\\b"):
        result = _resolve(profile_dirs, game_id=bad, core_name=bad, platform=bad)
        assert result["mappings"]["a"] == "cross"


def test_resolve_does_not_mutate_profile_files(profile_dirs):
    path = profile_dirs["devices"] / "054c_09cc.json"
    _write_json(path, {"mappings": {"a": "cross"}})
    before = path.read_text()
    _resolve(profile_dirs, game_id="missing")
    assert path.read_text() == before
    assert os.listdir(profile_dirs["games"]) == []
