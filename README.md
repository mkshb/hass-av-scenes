# AV Scenes — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/mkshb/hass-av-scenes.svg)](https://github.com/mkshb/hass-av-scenes/releases)
[![License](https://img.shields.io/github/license/mkshb/hass-av-scenes.svg)](LICENSE)

Activity-based AV control for Home Assistant — an open-source alternative to Logitech Harmony and Roomie Remote.

---

## Overview

AV Scenes controls the devices of a room (AV receiver, projector, TV, set-top box, lights, covers, power outlets) through named **activities** such as "TV" or "Movie". Starting an activity powers the devices it needs, waits until they are actually ready, applies sources, sound modes and volume, and runs any Home Assistant actions you attach. Switching to another activity only touches what differs; stopping shuts everything down in reverse order, with cool-down times and power outlets last.

---

## Features

| Feature | Description |
|---------|-------------|
| Device profiles | Each device is described once per room: entity, power outlet, readiness check, warm-up and cool-down time |
| Power outlets | Devices without standby power are supplied via a switch; shared outlets stay on as long as any device on them is needed |
| Readiness check | Waits until a device's entity is available instead of guessing delays; reloads its integration once to skip the `setup_retry` back-off |
| Cool-down | `delay_after_off` per device, e.g. 180 s for a projector before its outlet may be switched off |
| Smart switching | Devices the new activity does not use are switched off; shared devices stay on and are reconfigured |
| Hooks | `on_start` / `on_stop` take any Home Assistant actions — conditions, covers, lights, scripts |
| Cancelling | A stop during a long start takes effect immediately |
| Failure handling | A failed readiness check can abort the start; the room shows `error` with the reason |
| Restart-safe | The running activity survives a Home Assistant restart |
| Repairs | Entities that do not exist (typo, renamed entity) are reported in **Settings → Repairs** |
| Configuration panel | An admin page in the sidebar with a built-in guide: devices and activities as lists, each edited on its own page in short sections with help texts, using Home Assistant's own pickers; plus a YAML view |
| Remote control card | A dashboard card per room: power, activities, volume, d-pad, channels, playback and your own buttons — only what the running activity offers |
| Command routing | `av_scenes.send_command` sends a button (e.g. `volume_up`) to whichever device the running activity uses for it — from the card, automations or wall switches |
| 4 entity platforms | Scene, Switch, Sensor, Select — one virtual device per room |

---

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. **Integrations** → three dots top right → **Custom repositories**
3. Add `https://github.com/mkshb/hass-av-scenes`, category **Integration**
4. Find "AV Scenes" and click **Download**
5. Restart Home Assistant

HACS installs the release archive `av_scenes.zip`, which contains the built remote control card.

### Manual

1. Download `av_scenes.zip` from the latest [release](https://github.com/mkshb/hass-av-scenes/releases)
2. Extract it into `config/custom_components/av_scenes/`
3. Restart Home Assistant

A plain copy of the repository lacks the remote control card, which is built at release time; see [Development](#development) to build it yourself.

---

## Setup

1. **Settings** → **Devices & Services** → **+ Add Integration** → **AV Scenes**
2. Open **AV Scenes** in the sidebar (administrators only)
3. **Add room**, then add devices and activities and **Save**

### Configuration panel

The panel edits everything the [configuration](#configuration) below describes:

- **Devices** — entity and power outlet with Home Assistant's entity picker; boot time, wait times and readiness check as fields; own `commands` in a YAML field. Renaming a device ID updates every reference; a device that an activity still uses cannot be deleted.
- **Activities** — name, icon, position, devices in power-on order, steps (source and sound mode lists come from the device), remote button routing, and `on_start` / `on_stop` in Home Assistant's action editor, the same as in automations. The activity ID is part of the entity IDs and cannot be changed.
- **YAML** — the whole room as YAML, for anything the forms do not cover.

**Save** checks the configuration first: errors are shown with their exact place, unknown entities of the room as a warning you can confirm. If the configuration was changed elsewhere in the meantime (a second browser, the YAML editor below), the panel asks you to reload instead of overwriting it.

### YAML editor in the integration options

**Configure** on the integration opens the same configuration as YAML: **Add room**, **Edit room**, **Delete room** and **Edit whole configuration**, which shows all rooms as one YAML document — handy for backups and copying activities between rooms.

Every save is validated. Errors name the exact place, e.g. `rooms.wohnzimmer.activities.tv.devices.0: unknown device 'vu'`. Entities that do not exist in Home Assistant are listed as warnings that you can confirm or go back and fix. A device without power still counts as existing, because its entity stays in the entity registry.

Changes to the content of a room are applied immediately without interrupting a running activity. Adding, removing or renaming rooms or activities reloads the integration, since entities change.

---

## Configuration

A room consists of **devices** and **activities**:

```yaml
name: Wohnzimmer
devices:
  onkyo:
    entity_id: media_player.onkyo_receiver
    power_switch: switch.wz_steckdose_multimedia_5_4_grau
    ready: {timeout: 60, reload_integration: true, on_timeout: abort}
  beamer:
    entity_id: media_player.epson_ehtw7400
    power_switch: switch.wz_steckdose_beamer_5_3_schwarz
    ready: {timeout: 60, reload_integration: true, on_timeout: continue}
    delay_after_off: 180
  vu:
    entity_id: media_player.vu_as2b_de
    power_switch: switch.wz_steckdose_multimedia_5_4_grau
    ready: {timeout: 60, reload_integration: true, on_timeout: continue}
activities:
  tv:
    name: TV
    devices: [onkyo, beamer, vu]
    steps:
      - {type: set_source, device: onkyo, source: SAT}
      - {type: set_sound_mode, device: onkyo, sound_mode: THX}
      - {type: set_volume, device: onkyo, volume_level: 0.35}
    on_start:
      - if:
          - condition: numeric_state
            entity_id: sensor.wz_helligkeit
            above: 20000
        then:
          - action: cover.close_cover
            target: {area_id: wohnzimmer}
      - action: light.turn_on
        target: {entity_id: light.wz_ambiente}
        data: {brightness_pct: 15, color_temp_kelvin: 2400}
    on_stop:
      - action: cover.open_cover
        target: {area_id: wohnzimmer}
  musik:
    name: Musik
    devices: [onkyo]
    steps:
      - {type: set_source, device: onkyo, source: NET}
```

### Devices

| Key | Default | Description |
|-----|---------|-------------|
| `entity_id` | — | The entity that represents the device (required) |
| `name` | — | Optional display name |
| `power_switch` | — | Switch that supplies the device with power. Several devices may share one |
| `ready` | — | Readiness check before the device is switched on (see below) |
| `delay_after_power` | `0` | Boot time: seconds the device needs after its `power_switch` came on before it accepts commands. Counted from switching the outlet on, so devices on the same outlet boot in parallel. Skipped when the outlet was already on. Use it for devices that report `off` instead of `unavailable` while they have no power — the readiness check cannot tell those states apart |
| `delay_after_on` | `0` | Seconds to wait after switching the device on. Skipped when the device was already on |
| `delay_after_off` | `0` | Seconds the device needs after switching off before the next device is switched off or its power is cut |
| `commands` | — | Remote buttons as Home Assistant actions, see [Remote control](#remote-control) |

`ready` takes:

| Key | Default | Description |
|-----|---------|-------------|
| `entity_id` | the device | Check another entity, e.g. `remote.apple_tv`: the Apple TV integration reports its media player as `off` while it is not connected, while its remote is `on` only when connected |
| `state` | — | Wait for this state (or a list of states) instead of "not `unavailable`" |
| `timeout` | `60` | Seconds to wait for the entity |
| `reload_integration` | `false` | Reload the integration that provides the entity once, before waiting. This skips the back-off of an integration in `setup_retry`, which can otherwise take more than a minute after the device got power |
| `on_timeout` | `abort` | `abort` stops the start and puts the room into `error`; `continue` logs a warning and goes on |

The check also runs before a remote button (`send_command`) reaches the device: if the connection was lost while the activity runs, it is brought back first, then the command is sent. Example for an Apple TV:

```yaml
aptv:
  entity_id: media_player.apple_tv
  ready: {entity_id: remote.apple_tv, state: "on", timeout: 30, reload_integration: true, on_timeout: continue}
```

### Activities

| Key | Description |
|-----|-------------|
| `name` | Display name (defaults to the key) |
| `icon` | Icon in the remote control card, e.g. `mdi:television` |
| `order` | Position in lists; without it, activities are sorted by name. Home Assistant stores the configuration with sorted keys, so the order in which you write activities is not kept |
| `devices` | Devices the activity uses, in power-on order |
| `steps` | Settings applied once the devices are up |
| `on_start` | Home Assistant actions, run alongside the start |
| `on_stop` | Home Assistant actions, run alongside a stop |
| `remote` | Which device gets which remote buttons, and extra buttons, see [Remote control](#remote-control) |
| `commands` | Remote buttons only this activity has, see [Remote control](#remote-control) |

`on_start` and `on_stop` use the same syntax as scripts and automations: `action`, `if`/`then`, `choose`, `delay`, `wait_template`, `parallel` and so on. They run on a full stop only, not when switching to another activity.

### Steps

Every step has a `type` and may have `delay_after` (seconds to wait afterwards). `device` refers to a key in `devices`.

| Type | Parameters | Action |
|------|------------|--------|
| `set_source` | `device`, `source` | `media_player.select_source` |
| `set_volume` | `device`, `volume_level` (0–1) | `media_player.volume_set` |
| `set_sound_mode` | `device`, `sound_mode` | `media_player.select_sound_mode` |
| `set_brightness` | `device`, `brightness_pct`, `color_temp_kelvin`, `transition` | `light.turn_on` |
| `set_color_temp` | `device`, `color_temp_kelvin` | `light.turn_on` |
| `set_position` | `device`, `position` (0–100) | `cover.set_cover_position` |
| `set_tilt` | `device`, `tilt_position` (0–100) | `cover.set_cover_tilt_position` |
| `power_on` / `power_off` | `device` | Switch a device on or off in the middle of the sequence |
| `call_action` | `action`, `data`, `target` | Any Home Assistant action |
| `wait_available` | `device` or `entity_id`, `state`, `timeout`, `reload_integration`, `on_timeout` | Same as a device's `ready`, for any entity at any point |
| `delay` | `delay_after` | Only wait |

Every service call waits for the device to finish (`blocking`), at most 15 seconds. A failing step is logged and listed in the sensor's `warnings` attribute; the activity continues.

---

## What happens when

### Start

1. **Smart switching** — if another activity runs in the room, its devices that the new one does not use are switched off. Power outlets that are no longer needed are switched off in the background once those devices had their `delay_after_off`.
2. **Power** — all outlets of the activity's devices are switched on at once, so the devices boot in parallel.
3. **`on_start`** starts running alongside.
4. **Devices**, in order: boot time `delay_after_power` (only if its outlet was off), readiness check, switch on (only if off), `delay_after_on` (only if it was switched on).
5. **Steps**, in order.
6. When `on_start` has finished too, the activity is `active`.

### Stop

1. **`on_stop`** starts running alongside.
2. **Devices** in reverse order: switch off, then wait `delay_after_off`. A device that was already off only waits for what is left of its cool-down.
3. **Power outlets** are switched off last.

For the example above: VU+ off → projector off → 180 s cool-down → Onkyo off → both outlets off.

### Commands while something runs

A new command cancels whatever runs in the room: a stop during a long start takes effect immediately, and a stop from the `error` state switches off what the failed start had already powered. Sending the command that is already running just waits for it.

---

## Remote control

### The card

Add the card to any dashboard (**Edit dashboard → Add card → AV Scenes Remote**) and pick the room. Since Home Assistant 2026.6 the card picker also suggests it by entity: under **By entity**, open the area and the room's device ("AV: <room>") or pick one of its entities, and the card is offered with that room already set. Or in YAML:

```yaml
type: custom:av-scenes-remote-card
room: wohnzimmer
name: Living room   # optional title
```

The card shows the room's state with a power button (toggle), the activities as buttons, the start progress and errors, and — while an activity runs — the remote: volume rocker and slider, d-pad, channel rocker, navigation and playback keys and the activity's own and quick-select buttons. Only what the running activity offers is shown. Volume and arrow keys repeat while held. It works for every user, in the browser and in the Home Assistant app.

The integration registers the card as a dashboard resource itself (**Settings → Dashboards → Resources**, `/av_scenes_static/av-scenes-card.js?v=…`) and updates its version after every update, so browsers and the app load the current card instead of a cached one. Removing the integration removes the resource. With resources in YAML (`lovelace: resource_mode: yaml`), the card is loaded on every page instead; there is nothing to add in either case. A dashboard loaded in the few seconds of a restart before the integration is set up shows "Custom element doesn't exist"; reloading it once fixes that.

### Which device gets which button

Buttons belong to four groups. Each activity sends a group to one of its devices:

| Group | Commands | Default device |
|-------|----------|----------------|
| `volume` | `volume_up`, `volume_down`, `mute`, `volume_set` | First media player of the activity |
| `channels` | `channel_up`, `channel_down` | Last media player, if it is a separate source (e.g. a set-top box behind the receiver) |
| `transport` | `play_pause`, `play`, `pause`, `stop`, `next`, `previous` | Last media player |
| `navigation` | `up`, `down`, `left`, `right`, `ok`, `back`, `menu`, `home`, `info`, `guide`, `exit` | Last device with navigation `commands` |

Media players handle volume, channels and playback without any configuration (`media_player.volume_up`, `media_next_track`, …; set-top boxes such as Enigma2 map next/previous track to the channel keys). Override the defaults per activity, or hide a group with `null`:

```yaml
activities:
  tv:
    remote:
      volume: onkyo
      channels: vu
      transport: null
```

### Own commands and buttons

`commands` maps a command name to Home Assistant actions — on a device for every activity that uses it, or on an activity for that activity only. The variables `command`, `value` and (on devices) `entity_id` are available in templates. Own commands override the built-in ones.

Navigation keys need commands, since most media players have no actions for them. Enigma2 receivers (VU+, Dreambox) accept key codes through OpenWebif; the codes below are Linux input key codes — check them against your box:

```yaml
# configuration.yaml
rest_command:
  vu_key:
    url: "http://vu-as2b.local/api/remotecontrol?command={{ code }}"
```

```yaml
# AV Scenes room
devices:
  vu:
    entity_id: media_player.vu_as2b_de
    commands:
      up:    {action: rest_command.vu_key, data: {code: 103}}
      down:  {action: rest_command.vu_key, data: {code: 108}}
      left:  {action: rest_command.vu_key, data: {code: 105}}
      right: {action: rest_command.vu_key, data: {code: 106}}
      ok:    {action: rest_command.vu_key, data: {code: 352}}
      exit:  {action: rest_command.vu_key, data: {code: 174}}
      menu:  {action: rest_command.vu_key, data: {code: 139}}
      info:  {action: rest_command.vu_key, data: {code: 358}}
      guide: {action: rest_command.vu_key, data: {code: 365}}
activities:
  tv:
    icon: mdi:television
    order: 1
    remote:
      buttons:
        - guide
        - {command: netflix, name: Netflix, icon: mdi:netflix}
    commands:
      netflix:
        - action: media_player.select_source
          target: {entity_id: media_player.onkyo_receiver}
          data: {source: STRM BOX}
```

`buttons` lists extra buttons of the activity; each names a command (standard or own) with optional `name`, `icon` and `device`.

### Quick select

A button with `device` and `source` instead of `command` switches that media player to a source: an input of a receiver, or an app on an Apple TV, whose source list holds its installed apps. It runs `media_player.select_source`, after the device's readiness check like every other button. Without `name`, the button is labelled with the source.

```yaml
activities:
  apple_tv:
    remote:
      buttons:
        - {device: aptv, source: Netflix, icon: mdi:netflix}
        - {device: aptv, source: YouTube, icon: mdi:youtube}
        - {device: aptv, source: ARD Mediathek, name: ARD}
```

In the configuration panel, quick select has its own list under **Remote control**: pick the device, then the source from its list. The integration remembers the last source list of every configured media player, so the list is there even while the device is off; an Apple TV reports its apps only while it is connected, so start it once after adding it. A name that is not in the list can be typed in.

`av_scenes.send_command` does the same with `command: select_source`, `value: <source>` and `device`.

A command is resolved in this order: the activity's own `commands`, then the device of its group (own `commands` or built-in action), then the first device of the activity that defines it — so digit keys `"0"`–`"9"` only need to exist on the set-top box.

---

## Entities

One virtual device per room (linked to the area of the same name) with four entities. Entity names and state labels are translated (English and German); the state values themselves are stable keys, so automations work regardless of the language. Entity IDs are generated by Home Assistant from the translated names and may differ per installation — look them up on the room's device page.

### Select — Scene

Shows the running activity and starts, switches or stops activities.

| Option (state value) | Shown as | Meaning |
|----------------------|----------|---------|
| Activity name | Activity name | That activity is active — select another one to switch |
| `idle` | `—` | Idle; selecting it stops the current activity |
| `starting` / `stopping` | `Starting …` / `Stopping …` | Transition in progress (read-only) |
| `error` | `Error` | The last start was aborted (read-only) — see the sensor |

### Sensor — Activity

**State:** `idle` · `starting` · `active` · `stopping` · `error`

| Attribute | Description |
|-----------|-------------|
| `activity_id`, `activity_name` | The current activity, or `null` |
| `available_activities` | Names of all activities of the room |
| `current_step`, `total_steps`, `step_progress_pct` | Progress (devices and steps) |
| `error` | Why the last start was aborted |
| `warnings` | Steps that failed during the last start |
| `devices`, `steps` | Summary of the current activity |

An aborted start is also reported in **Settings → Repairs**; the entry disappears with the next start or stop of the room.

### Switch — Active

`on` while an activity runs, starts or failed. `turn_on` starts the last used activity (or the first one), `turn_off` stops.

### Scene — one per activity

One scene per activity; activating it starts the activity.

---

## Actions

```yaml
# Start an activity (by key or display name)
action: av_scenes.start_activity
data:
  room: wohnzimmer
  activity: tv

# Stop the current activity
action: av_scenes.stop_activity
data:
  room: wohnzimmer

# Stop if something runs, otherwise start (default: the last used activity)
action: av_scenes.toggle_activity
data:
  room: wohnzimmer
  activity: tv        # optional

# Send a remote button to the device the running activity uses for it
action: av_scenes.send_command
data:
  room: wohnzimmer
  command: volume_up  # or volume_set with value: 0.4, ok, channel_up, an own command …
  device: vu          # optional: this device instead, works while nothing runs

# Reload the configuration
action: av_scenes.reload
```

The room ID is the key in the configuration (shown in **Edit whole configuration**).

The actions return when the activity has fully started or stopped, which can take minutes with cool-down times. Use `mode: parallel` in automations that call them, so that a second trigger (e.g. a stop while starting) is not swallowed by `mode: single`.

### Example: KNX push button

```yaml
alias: Living room TV push button
mode: parallel
triggers:
  - trigger: knx.telegram
    destination: "5/1/10"
    group_value_read: false
    group_value_response: false
actions:
  - action: av_scenes.toggle_activity
    data:
      room: wohnzimmer
      activity: tv
```

With a rocker that sends separate on/off telegrams, use `start_activity` and `stop_activity` instead. Volume buttons on the wall work the same way with `send_command`, and always reach the device of the running activity.

---

## Upgrading from 0.6 and earlier

The configuration is migrated automatically on the first start (config entry version 1 → 2). Nothing is lost:

- Every entity used in a step becomes a device of its room.
- `power_on` steps become the activity's device list; their `delay_after` becomes the device's `delay_after_on`.
- The cool-down while stopping keeps its previous value: the largest `delay_after` of the device's steps becomes `delay_after_off`.
- Entities that had steps but no `power_on` step (e.g. lights, covers) were switched off when stopping; this is kept as `on_stop` actions you can now edit.
- Light brightness (0–255) becomes `brightness_pct`; color temperature in mireds becomes `color_temp_kelvin`.
- Unknown keys are kept.

Two behaviours change: all devices are switched on before the settings steps run, and `on_stop` actions (including the migrated ones) run on a full stop, not when switching activities.

**Make a backup before upgrading.** A migrated configuration cannot be loaded by older versions.

---

## Troubleshooting

- **Logs:** **Settings → Devices & Services → AV Scenes → ⋮ → Enable debug logging**. Every step, wait and reload is logged with its room.
- **Device not ready in time:** raise `ready.timeout`, and set `reload_integration: true` for integrations that go into `setup_retry` without power.
- **Repairs entry "entity is missing":** the entity was renamed or removed; fix `entity_id` in the room.

---

## Development

```bash
pip install -r requirements_test.txt
pytest
```

The remote control card and the configuration panel live in `frontend/` (Lit, TypeScript, esbuild):

```bash
cd frontend
npm ci
npm run build   # writes av-scenes-card.js and av-scenes-panel.js to custom_components/av_scenes/frontend/
```

The build output is not tracked in git. Publishing a GitHub release runs `.github/workflows/release.yml`, which builds the card and attaches `av_scenes.zip`. The release tag sets the version in the archive (e.g. `v0.7.0-beta.1` for a pre-release that HACS offers under "Show beta versions").

---

## License & Support

- License: [MIT](LICENSE)
- Bugs & feature requests: [GitHub Issues](https://github.com/mkshb/hass-av-scenes/issues)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
