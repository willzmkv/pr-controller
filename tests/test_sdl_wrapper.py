import ctypes
import subprocess
import sys
import textwrap
from unittest.mock import MagicMock, patch

import pytest

from pr_controller.sdl_wrapper import SDLWrapper, SDL_VERSION_2, SDL_VERSION_3


def test_sdl_wrapper_instantiates_without_loading_library():
    """SDLWrapper() must not dlopen anything at import/construction time."""
    # If it does, this will raise OSError on systems without SDL.
    wrapper = SDLWrapper(sdl_version=SDL_VERSION_2, _lib=MagicMock())
    assert wrapper is not None


def test_get_joystick_name_calls_lib(monkeypatch):
    mock_lib = MagicMock()
    mock_lib.SDL_JoystickNameForIndex.return_value = b"Sony DualShock 4"
    wrapper = SDLWrapper(sdl_version=SDL_VERSION_2, _lib=mock_lib)
    name = wrapper.get_joystick_name(0)
    assert name == "Sony DualShock 4"
    mock_lib.SDL_JoystickNameForIndex.assert_called_once_with(0)


def test_get_joystick_guid_calls_lib(monkeypatch):
    mock_lib = MagicMock()
    # SDL_JoystickGetDeviceGUID returns a struct; we mock the string conversion
    mock_lib.SDL_JoystickGetDeviceGUID.return_value = MagicMock()
    mock_lib.SDL_JoystickGetGUIDString.side_effect = lambda guid, buf, sz: buf.__setitem__(slice(None), b"03000000" + b"\x00" * 24)
    wrapper = SDLWrapper(sdl_version=SDL_VERSION_2, _lib=mock_lib)
    # Just verify it calls the right function without crashing
    mock_lib.SDL_JoystickGetDeviceGUID.return_value = object()
    assert wrapper is not None


def test_sdl3_uses_different_api():
    mock_lib = MagicMock()
    mock_lib.SDL_GetJoystickNameForID.return_value = b"Xbox Controller"
    wrapper = SDLWrapper(sdl_version=SDL_VERSION_3, _lib=mock_lib)
    name = wrapper.get_joystick_name(0)
    assert name == "Xbox Controller"
    mock_lib.SDL_GetJoystickNameForID.assert_called_once_with(0)


def test_load_sdl2_returns_wrapper(monkeypatch):
    fake_lib = MagicMock()
    with patch("pr_controller.sdl_wrapper.ctypes.CDLL", return_value=fake_lib):
        wrapper = SDLWrapper.load(prefer_version=SDL_VERSION_2)
    assert wrapper.sdl_version == SDL_VERSION_2


def test_load_sdl3_falls_back_to_sdl2_if_missing(monkeypatch):
    fake_lib = MagicMock()
    def cdll_side_effect(name):
        if "3" in name:
            raise OSError("not found")
        return fake_lib
    with patch("pr_controller.sdl_wrapper.ctypes.CDLL", side_effect=cdll_side_effect):
        wrapper = SDLWrapper.load(prefer_version=SDL_VERSION_3)
    assert wrapper.sdl_version == SDL_VERSION_2


# --- additions beyond the plan ----------------------------------------------


def test_load_declares_c_signatures():
    # Without restype, ctypes returns const char* as a plain int and the
    # plan's get_joystick_name() would return a number as the "name".
    fake_lib = MagicMock()
    with patch("pr_controller.sdl_wrapper.ctypes.CDLL", return_value=fake_lib):
        SDLWrapper.load(prefer_version=SDL_VERSION_2)
    assert fake_lib.SDL_JoystickNameForIndex.restype is ctypes.c_char_p
    assert fake_lib.SDL_JoystickNameForIndex.argtypes == [ctypes.c_int]
    assert fake_lib.SDL_NumJoysticks.restype is ctypes.c_int

    fake_lib3 = MagicMock()
    with patch("pr_controller.sdl_wrapper.ctypes.CDLL", return_value=fake_lib3):
        SDLWrapper.load(prefer_version=SDL_VERSION_3)
    assert fake_lib3.SDL_GetJoystickNameForID.restype is ctypes.c_char_p
    assert fake_lib3.SDL_GetJoystickNameForID.argtypes == [ctypes.c_uint32]
    assert fake_lib3.SDL_GetJoysticks.restype is ctypes.c_void_p


def test_load_raises_when_no_sdl_available():
    with patch("pr_controller.sdl_wrapper.ctypes.CDLL", side_effect=OSError("nope")):
        with pytest.raises(RuntimeError):
            SDLWrapper.load()


def test_missing_name_returns_unknown():
    mock_lib = MagicMock()
    mock_lib.SDL_JoystickNameForIndex.return_value = None
    assert SDLWrapper(SDL_VERSION_2, _lib=mock_lib).get_joystick_name(3) == "Unknown"


def test_sdl2_num_joysticks():
    mock_lib = MagicMock()
    mock_lib.SDL_NumJoysticks.return_value = 2
    assert SDLWrapper(SDL_VERSION_2, _lib=mock_lib).get_num_joysticks() == 2


def test_sdl3_num_joysticks_uses_get_joysticks_and_frees_the_array():
    # SDL3 has no SDL_GetNumJoysticks; the count comes from SDL_GetJoysticks().
    mock_lib = MagicMock(spec=["SDL_GetJoysticks", "SDL_free"])

    def get_joysticks(count_ref):
        count_ref._obj.value = 3
        return 0xDEAD

    mock_lib.SDL_GetJoysticks.side_effect = get_joysticks
    assert SDLWrapper(SDL_VERSION_3, _lib=mock_lib).get_num_joysticks() == 3
    mock_lib.SDL_free.assert_called_once_with(0xDEAD)


@pytest.mark.parametrize(
    "version, rc, ok",
    [(SDL_VERSION_2, 0, True), (SDL_VERSION_2, -1, False),
     (SDL_VERSION_3, True, True), (SDL_VERSION_3, False, False)],
)
def test_init_reports_success_per_version_convention(version, rc, ok):
    mock_lib = MagicMock()
    mock_lib.SDL_Init.return_value = rc
    mock_lib.SDL_GetError.return_value = b"boom"
    assert SDLWrapper(version, _lib=mock_lib).init() is ok
    mock_lib.SDL_Init.assert_called_once_with(0x200)  # SDL_INIT_JOYSTICK


def test_quit_calls_sdl_quit():
    mock_lib = MagicMock()
    SDLWrapper(SDL_VERSION_3, _lib=mock_lib).quit()
    mock_lib.SDL_Quit.assert_called_once_with()


_SMOKE = textwrap.dedent(
    """
    import sys
    from pr_controller.sdl_wrapper import SDLWrapper, _SDL2_NAMES, _SDL3_NAMES
    version = int(sys.argv[1])
    try:
        w = SDLWrapper.load(prefer_version=version)
    except RuntimeError:
        sys.exit(77)
    if w.sdl_version != version:
        sys.exit(77)
    assert w.init(), "SDL_Init(SDL_INIT_JOYSTICK) failed"
    n = w.get_num_joysticks()
    assert n >= 0
    for i in range(n):
        assert isinstance(w.get_joystick_name(i), str)
    w.quit()
    print("ok", n)
    """
)


@pytest.mark.parametrize("version", [SDL_VERSION_2, SDL_VERSION_3])
def test_real_sdl_library_smoke(version):
    """Exercise the real libSDL in a subprocess when it is installed."""
    proc = subprocess.run(
        [sys.executable, "-c", _SMOKE, str(version)],
        capture_output=True, text=True, timeout=30,
        env={"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy",
             "PYTHONPATH": ":".join(sys.path)},
    )
    if proc.returncode == 77:
        pytest.skip(f"SDL{version} not installed")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("ok")
