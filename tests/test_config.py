import importlib

import pytest

from pr_controller.config import (  # noqa: F401  (import surface check)
    GAMES_PROFILE_DIR,
    CORES_PROFILE_DIR,
    PLATFORMS_PROFILE_DIR,
    DEVICES_PROFILE_DIR,
    RETROARCH_AUTOCONFIG_DIR,
    ESDE_CONFIG_DIR,
)


@pytest.fixture(autouse=True)
def _restore_config_module():
    """Reload pr_controller.config after monkeypatch has restored the env.

    Autouse fixtures are set up before (and torn down after) ``monkeypatch``,
    so the reload below sees the original environment and later tests do not
    inherit the paths computed from this module's fake HOME/XDG values.
    """
    yield
    import pr_controller.config as cfg

    importlib.reload(cfg)


def test_games_profile_dir_is_under_xdg_config(monkeypatch):
    monkeypatch.setenv("HOME", "/home/arcade")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    # Re-import to pick up env change
    import pr_controller.config as cfg

    importlib.reload(cfg)
    assert cfg.GAMES_PROFILE_DIR == "/home/arcade/.config/project-r/input/games"


def test_devices_profile_dir_uses_xdg_config_home(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/cfg")
    import pr_controller.config as cfg

    importlib.reload(cfg)
    assert cfg.DEVICES_PROFILE_DIR == "/custom/cfg/project-r/input/devices"


def test_output_paths_follow_xdg_and_os_image(monkeypatch):
    monkeypatch.setenv("HOME", "/home/arcade")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for var in (
        "PR_CONTROLLER_RETROARCH_AUTOCONFIG_DIR",
        "PR_CONTROLLER_ESDE_INPUT",
        "PR_CONTROLLER_SDL_DB",
        "PR_BUILDER_SOCKET",
    ):
        monkeypatch.delenv(var, raising=False)
    import pr_controller.config as cfg

    importlib.reload(cfg)
    assert cfg.CONFIG_BASE == "/home/arcade/.config/project-r"
    assert cfg.RETROARCH_AUTOCONFIG_DIR == "/home/arcade/.config/retroarch/autoconfig"
    # ES-DE 3.x keeps its settings under ~/ES-DE/settings/
    assert cfg.ESDE_INPUT_PATH == "/home/arcade/ES-DE/settings/es_input.xml"
    # Must match SDL_GAMECONTROLLERCONFIG_FILE exported by project-r-os .xinitrc
    assert cfg.SDL_DB_PATH == "/home/arcade/.config/project-r/input/sdl_gamecontrollerdb.txt"
    assert cfg.PR_BUILDER_SOCKET == "/run/project-r/pr-builder.sock"


def test_output_paths_can_be_overridden_by_env(monkeypatch):
    monkeypatch.setenv("PR_CONTROLLER_RETROARCH_AUTOCONFIG_DIR", "/x/ra")
    monkeypatch.setenv("PR_CONTROLLER_ESDE_INPUT", "/x/es_input.xml")
    monkeypatch.setenv("PR_CONTROLLER_SDL_DB", "/x/db.txt")
    monkeypatch.setenv("PR_BUILDER_SOCKET", "/x/b.sock")
    import pr_controller.config as cfg

    importlib.reload(cfg)
    assert cfg.RETROARCH_AUTOCONFIG_DIR == "/x/ra"
    assert cfg.ESDE_INPUT_PATH == "/x/es_input.xml"
    assert cfg.SDL_DB_PATH == "/x/db.txt"
    assert cfg.PR_BUILDER_SOCKET == "/x/b.sock"


def test_empty_xdg_config_home_falls_back_to_home(monkeypatch):
    monkeypatch.setenv("HOME", "/home/arcade")
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    monkeypatch.delenv("PR_CONTROLLER_RETROARCH_AUTOCONFIG_DIR", raising=False)
    import pr_controller.config as cfg

    importlib.reload(cfg)
    assert cfg.RETROARCH_AUTOCONFIG_DIR == "/home/arcade/.config/retroarch/autoconfig"
