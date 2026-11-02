"""Thin ctypes wrapper over the SDL2 / SDL3 joystick API.

All SDL calls live here so higher-level code can be tested with a mock
library (``SDLWrapper(version, _lib=MagicMock())``). Nothing is dlopen'ed
until :meth:`SDLWrapper.load` is called.

SDL2 addresses joysticks by *device index*; SDL3 by *joystick instance ID*.
The ``device_index`` arguments below take whichever the loaded version uses.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import logging

log = logging.getLogger(__name__)

SDL_VERSION_2 = 2
SDL_VERSION_3 = 3

SDL_INIT_JOYSTICK = 0x00000200  # same value in SDL2 and SDL3

_SDL2_NAMES = ["libSDL2-2.0.so.0", "libSDL2.so", "SDL2"]
_SDL3_NAMES = ["libSDL3.so.0", "libSDL3.so", "SDL3"]

# name -> (argtypes, restype)
_SIGNATURES = {
    SDL_VERSION_2: {
        "SDL_Init": ([ctypes.c_uint32], ctypes.c_int),
        "SDL_Quit": ([], None),
        "SDL_GetError": ([], ctypes.c_char_p),
        "SDL_NumJoysticks": ([], ctypes.c_int),
        "SDL_JoystickNameForIndex": ([ctypes.c_int], ctypes.c_char_p),
    },
    SDL_VERSION_3: {
        "SDL_Init": ([ctypes.c_uint32], ctypes.c_bool),
        "SDL_Quit": ([], None),
        "SDL_GetError": ([], ctypes.c_char_p),
        "SDL_free": ([ctypes.c_void_p], None),
        "SDL_GetJoysticks": ([ctypes.POINTER(ctypes.c_int)], ctypes.c_void_p),
        "SDL_GetJoystickNameForID": ([ctypes.c_uint32], ctypes.c_char_p),
    },
}


def _declare_signatures(lib: object, version: int) -> None:
    """Set argtypes/restype so ctypes marshals pointers and strings correctly."""
    for name, (argtypes, restype) in _SIGNATURES[version].items():
        try:
            fn = getattr(lib, name)
        except AttributeError:
            log.warning("SDL%d library lacks %s", version, name)
            continue
        fn.argtypes = argtypes
        fn.restype = restype


class SDLWrapper:
    """Thin wrapper around SDL2 or SDL3 joystick API.

    All ctypes calls are isolated here. Pass _lib=MagicMock() in tests.
    """

    def __init__(self, sdl_version: int, _lib: object) -> None:
        self.sdl_version = sdl_version
        self._lib = _lib

    # --- lifecycle ---

    def init(self) -> bool:
        """Initialise SDL's joystick subsystem. Returns True on success."""
        rc = self._lib.SDL_Init(SDL_INIT_JOYSTICK)
        ok = bool(rc) if self.sdl_version == SDL_VERSION_3 else rc == 0
        if not ok:
            log.warning("SDL_Init failed: %s", self.get_error())
        return ok

    def quit(self) -> None:
        self._lib.SDL_Quit()

    def get_error(self) -> str:
        raw = self._lib.SDL_GetError()
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)

    # --- public API (same for callers regardless of SDL version) ---

    def get_joystick_name(self, device_index: int) -> str:
        """Return the human-readable name for the joystick at device_index."""
        if self.sdl_version == SDL_VERSION_3:
            raw = self._lib.SDL_GetJoystickNameForID(device_index)
        else:
            raw = self._lib.SDL_JoystickNameForIndex(device_index)
        if raw is None:
            return "Unknown"
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)

    def get_num_joysticks(self) -> int:
        if self.sdl_version == SDL_VERSION_3:
            # SDL3 dropped SDL_GetNumJoysticks(); SDL_GetJoysticks() returns an
            # SDL_malloc'ed ID array plus its length.
            count = ctypes.c_int(0)
            ids = self._lib.SDL_GetJoysticks(ctypes.byref(count))
            if ids:
                self._lib.SDL_free(ids)
            return int(count.value)
        return int(self._lib.SDL_NumJoysticks())

    # --- factory ---

    @classmethod
    def load(cls, prefer_version: int = SDL_VERSION_3) -> "SDLWrapper":
        """Try to load the preferred SDL version; fall back to the other.

        Raises RuntimeError if neither SDL2 nor SDL3 is found.
        """
        primary   = (_SDL3_NAMES, SDL_VERSION_3) if prefer_version == SDL_VERSION_3 else (_SDL2_NAMES, SDL_VERSION_2)
        secondary = (_SDL2_NAMES, SDL_VERSION_2) if prefer_version == SDL_VERSION_3 else (_SDL3_NAMES, SDL_VERSION_3)

        for names, version in (primary, secondary):
            for name in names:
                try:
                    lib = ctypes.CDLL(name)
                except OSError:
                    continue
                _declare_signatures(lib, version)
                log.info("Loaded SDL%d (%s)", version, name)
                return cls(sdl_version=version, _lib=lib)

        raise RuntimeError("Neither SDL2 nor SDL3 could be loaded. Install sdl2-compat or sdl3.")
