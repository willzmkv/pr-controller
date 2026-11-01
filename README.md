# pr-controller

> Project-R controller daemon — SDL2/SDL3 hotplug detection with 3-level profile system.

**Language:** Python 3.11+ · **Status:** Pre-alpha · [Implementation Plan](https://github.com/willzmkv/project-r-os/blob/main/ROADMAP.md#pr-controller--controller-daemon)

## What it does

Monitors udev for controller hotplug events. Resolves the correct button mapping via a 3-level profile hierarchy and writes configs for RetroArch, ES-DE, and SDL gamecontrollerdb.

## Profile Resolution (3 levels)

```
game profile  >  core/platform profile  >  device profile (from vendor/product ID)
```

Higher levels override lower. Falls back to device_db defaults when no JSON file exists.

## Auto-Detection

| Hardware | Layout |
|---|---|
| Sony DualShock/DualSense | PlayStation |
| Xbox / xinput controllers | Xbox |
| Generic / SNES-style | SNES |

## Architecture

- `device_db.py` — vendor/product ID → layout + default mappings
- `profile_manager.py` — 3-level deep-merge resolution
- `writers/` — RetroArch autoconfig, ES-DE XML, SDL gamecontrollerdb
- `sdl_wrapper.py` — ctypes abstraction (SDL3 → SDL2 fallback)
- `daemon.py` — pyudev monitor loop, notifies pr-builder on connect/disconnect

## License

GPL-3.0
