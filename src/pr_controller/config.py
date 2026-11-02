"""Filesystem locations and IPC endpoints used by pr-controller.

All values are computed at import time from HOME / XDG_CONFIG_HOME and the
optional PR_* overrides, so a systemd unit can relocate any output with an
``Environment=`` line.
"""
import os

_HOME = os.environ.get("HOME") or os.path.expanduser("~")
# An empty XDG_CONFIG_HOME must be treated as unset (XDG Base Directory spec).
_XDG = os.environ.get("XDG_CONFIG_HOME") or os.path.join(_HOME, ".config")

# ~/.config/project-r — profile_manager.resolve_profile(config_base=...) root
CONFIG_BASE = os.path.join(_XDG, "project-r")
_BASE = os.path.join(CONFIG_BASE, "input")

GAMES_PROFILE_DIR = os.path.join(_BASE, "games")
CORES_PROFILE_DIR = os.path.join(_BASE, "cores")
PLATFORMS_PROFILE_DIR = os.path.join(_BASE, "platforms")
DEVICES_PROFILE_DIR = os.path.join(_BASE, "devices")

# RetroArch's default joypad_autoconfig_dir on Linux.
RETROARCH_AUTOCONFIG_DIR = os.environ.get(
    "PR_CONTROLLER_RETROARCH_AUTOCONFIG_DIR"
) or os.path.join(_XDG, "retroarch", "autoconfig")

# ES-DE 3.x keeps its settings in ~/ES-DE/settings/ (see project-r-os).
ESDE_CONFIG_DIR = os.path.join(_HOME, "ES-DE", "settings")
ESDE_INPUT_PATH = os.environ.get("PR_CONTROLLER_ESDE_INPUT") or os.path.join(
    ESDE_CONFIG_DIR, "es_input.xml"
)

# Must match SDL_GAMECONTROLLERCONFIG_FILE exported by the session
# (project-r-os ~/.xinitrc), which is how SDL2/SDL3 games pick it up.
SDL_DB_PATH = os.environ.get("PR_CONTROLLER_SDL_DB") or os.path.join(
    _BASE, "sdl_gamecontrollerdb.txt"
)

# Same variable name and default as pr-builder's own unit.
PR_BUILDER_SOCKET = os.environ.get("PR_BUILDER_SOCKET") or "/run/project-r/pr-builder.sock"
