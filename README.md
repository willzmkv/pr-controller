# pr-controller

> Project-R controller daemon — udev gamepad hotplug, vendor/product auto-mapping, a 3-level profile system and config writers for RetroArch, ES-DE and native SDL2/SDL3 ports.

**Language:** Python 3.11+ · **Status:** Pre-alpha · [Implementation Plan](https://github.com/willzmkv/project-r-os/blob/main/ROADMAP.md#pr-controller--controller-daemon)

## What it does

```
udev add (ID_INPUT_JOYSTICK=1, /dev/input/event*)      + coldplug at start-up
  → vendor/product ID (USB ID_VENDOR_ID/ID_MODEL_ID, Bluetooth via parent PRODUCT=)
  → resolve_profile(): game > core/platform > device file > built-in device_db
  → writers: RetroArch autoconfig · ES-DE es_input.xml · SDL gamecontrollerdb
  → controller_added → pr-builder (best-effort)
udev remove → controller_removed → pr-builder (written configs are kept)
```

Touchpads, motion sensors, `jsN` and parent `inputN` nodes are ignored; only a
pad's evdev node is configured. Errors in one writer or one event are logged
and never stop the daemon.

## Auto-detection (`device_db.py`)

| Hardware | vendor:product | Layout |
|---|---|---|
| DualShock 4 (both revisions), DualSense, DualSense Edge | `054c:09cc` `054c:05c4` `054c:0ce6` `054c:0df2` | `playstation` |
| Xbox 360, One, One S, Series | `045e:028e` `045e:02ea` `045e:02fd` `045e:0b12` | `xbox` |
| anything else | — | `snes` (named from udev `NAME`/`ID_MODEL`) |

## Profiles

All under `$XDG_CONFIG_HOME/project-r/input/` (default `~/.config/project-r/input/`).
Each level is deep-merged over the one below; the most specific wins.

| Priority | File | Notes |
|---|---|---|
| 1 | `games/{game_id}.json` | per game |
| 2 | `cores/{core_name}.json` | per RetroArch core; beats platform |
| 2 | `platforms/{platform}.json` | `steam`, `heroic`, `lutris`, … |
| 3 | `devices/{vendor}_{product}.json` | lowercase hex, e.g. `054c_09cc.json` |
| — | built-in `device_db` | always the base layer |

Names containing `/`, `\` or a leading `.` are rejected. Non-object or broken
JSON is logged and ignored.

Profile shape (every key optional in a file):

```json
{
  "device_name": "Sony DualShock 4",
  "layout": "playstation",
  "mappings": {"a": "cross", "b": "circle", "x": "square", "y": "triangle",
               "start": "options", "select": "share", "up": "dpad_up"},
  "button_indices": {"cross": 0, "circle": 1, "square": 3, "triangle": 2,
                     "share": 8, "options": 9, "dpad_up": "h0up"}
}
```

- `mappings`: generic, position-based name (`a` bottom, `b` right, `x` left,
  `y` top, `start`, `select`, `l1` `r1` `l2` `r2` `l3` `r3`, `up` `down`
  `left` `right`) → device button name. `null` unmaps a button.
- `button_indices`: device button name → joystick button index (int) or hat
  direction (`h<N>up|down|left|right`). Indices are in the evdev order that
  RetroArch's udev driver uses; the values above are illustrative, so check
  them on the real pad (e.g. RetroArch's input test) before relying on them.
- `vendor_id` / `product_id` are always set from the physical device.

## Files written

| Consumer | Default path | Override env |
|---|---|---|
| RetroArch (udev driver) | `~/.config/retroarch/autoconfig/<device_name>.cfg` | `PR_CONTROLLER_RETROARCH_AUTOCONFIG_DIR` |
| ES-DE 3.x | `~/ES-DE/settings/es_input.xml` | `PR_CONTROLLER_ESDE_INPUT` |
| SDL2/SDL3 games | `~/.config/project-r/input/sdl_gamecontrollerdb.txt` | `PR_CONTROLLER_SDL_DB` |

- **A writer only writes when at least one input resolves through
  `mappings` → `button_indices`.** An empty config would shadow the consumer's
  own built-in mapping, so without indices the file is left untouched.
- RetroArch: one file per device, `input_vendor_id`/`input_product_id` in
  decimal, RetroPad naming (our `a` → `input_b`, `x` → `input_y`, …).
- ES-DE: upserts one `<inputConfig type="joystick">` per device (keyed by SDL
  GUID + name), keeping the keyboard, other pads, ES-DE's own
  `type="controller"` entries and `<inputAction>`. Unparsable files are left alone.
- SDL: upserts the `platform:Linux` line for the device GUID
  (`030000004c050000cc09000000000000` for a DS4, CRC and version zeroed),
  keeping comments, other lines, and fields we do not model (sticks, `guide`,
  axis triggers) from an existing line. The session must export
  `SDL_GAMECONTROLLERCONFIG_FILE` pointing at this file; project-r-os
  `~/.xinitrc` already does.
- All writes are atomic (temp file + rename).

## IPC contract

### Outbound — pr-controller → pr-builder

- Socket: `/run/project-r/pr-builder.sock` (env `PR_BUILDER_SOCKET`; dir owned
  by `arcade:arcade`, created by pr-mediad's tmpfiles.d / pr-builder's unit)
- Framing: connect, send **one newline-terminated UTF-8 JSON line**,
  disconnect. No reply. 2 s timeout on connect/send.
- Best-effort: if the socket is missing, refused or stalls, pr-controller logs
  it and carries on.

```json
{"type":"controller_added","event":"controller_added","profile":{"device_name":"Sony DualShock 4","vendor_id":"054c","product_id":"09cc","layout":"playstation","mappings":{"a":"cross","…":"…"},"button_indices":{}}}
{"type":"controller_removed","event":"controller_removed","profile":{"vendor_id":"054c","product_id":"09cc","device_node":"/dev/input/event7"}}
```

| field | notes |
|---|---|
| `type` | event name; pr-builder's server dispatches on `type` |
| `event` | same value; the key the pr-controller plan specified |
| `profile` | full resolved profile on add; IDs + device node on remove |

> **Contract mismatch (pr-builder v0.1):** pr-builder's server only handles
> `type == "media_inserted"`. It accepts this line and logs
> `Unknown event type: controller_added` (checked against its real `Server`).
> No controller events are consumed yet; pr-controller keeps sending them
> best-effort so pr-builder can adopt them without a change here.

pr-controller has no inbound socket.

## Run

```bash
pip install -e .
pr-controller            # or: python -m pr_controller.daemon  (-v for debug logs)
```

`pr-controller.service` is a system unit running as `User=arcade` with
`HOME=/home/arcade` (installed by the PKGBUILD, enabled by project-r-os with
`systemctl enable pr-controller`). udev netlink monitoring needs no extra
privileges.

| env var | default |
|---|---|
| `PR_BUILDER_SOCKET` | `/run/project-r/pr-builder.sock` |
| `PR_CONTROLLER_RETROARCH_AUTOCONFIG_DIR` | `$XDG_CONFIG_HOME/retroarch/autoconfig` |
| `PR_CONTROLLER_ESDE_INPUT` | `~/ES-DE/settings/es_input.xml` |
| `PR_CONTROLLER_SDL_DB` | `$XDG_CONFIG_HOME/project-r/input/sdl_gamecontrollerdb.txt` |

## Architecture

- `config.py` — paths and env overrides
- `device_db.py` — vendor/product ID → layout + default mappings
- `profile_manager.py` — 3-level deep-merge resolution
- `writers/` — RetroArch autoconfig, ES-DE XML, SDL gamecontrollerdb (`_common.py`: binding parser, SDL GUID, atomic write)
- `sdl_wrapper.py` — ctypes SDL3 → SDL2 fallback (`init`, joystick count/names)
- `daemon.py` — pyudev monitor + coldplug, writers, pr-builder notifications

## Test

Tests mock udev and SDL; no controller is needed.

```bash
pip install -e ".[dev]"
pytest -v
```

The two `test_real_sdl_library_smoke` tests load the real libSDL2/libSDL3 in a
subprocess and are skipped when the library is not installed.

## Known gaps

- **No button-index discovery yet.** `button_indices` only comes from profile
  files, so out of the box nothing is written and RetroArch/ES-DE/SDL keep
  their built-in mappings. Planned: read SDL's mapping string per device
  (with HIDAPI off so indices match evdev/RetroArch udev order). Needs real
  pads to validate.
- **Axes are not modelled** (sticks, analog L2/R2). The RetroArch/ES-DE files
  carry buttons and hats only; the SDL line keeps axes only if an earlier line
  for that GUID had them.
- **ES-DE format:** entries use the classic `type="joystick"` format from the
  plan. ES-DE 3.x maps pads through SDL's GameController API
  (`type="controller"`), so in practice it is driven by the SDL DB above.
- **No game/core context source:** the daemon resolves with
  `game_id=core_name=platform=None`; nothing tells it which game is running yet.
- The SDL wrapper is not used by the daemon yet (udev already reports hotplug).
- RetroArch must read `~/.config/retroarch/autoconfig` (its Linux default
  `joypad_autoconfig_dir`).

## License

GPL-3.0
