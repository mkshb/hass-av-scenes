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
| 4 entity platforms | Scene, Switch, Sensor, Select — one virtual device per room |

---

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. **Integrations** → three dots top right → **Custom repositories**
3. Add `https://github.com/mkshb/hass-av-scenes`, category **Integration**
4. Find "AV Scenes" and click **Download**
5. Restart Home Assistant

### Manual

1. Download the latest release from [Releases](https://github.com/mkshb/hass-av-scenes/releases)
2. Copy `custom_components/av_scenes` into your `config/custom_components/` directory
3. Restart Home Assistant

---

## Setup

1. **Settings** → **Devices & Services** → **+ Add Integration** → **AV Scenes**
2. Click **Configure** on the integration
3. **Add room** — pick a Home Assistant area or enter a name
4. Describe devices and activities in the YAML editor that opens (see below) and save

The menu also offers **Edit room**, **Delete room** and **Edit whole configuration**, which shows all rooms as one YAML document — handy for backups and copying activities between rooms.

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
| `delay_after_on` | `0` | Seconds to wait after switching the device on. Skipped when the device was already on |
| `delay_after_off` | `0` | Seconds the device needs after switching off before the next device is switched off or its power is cut |

`ready` takes:

| Key | Default | Description |
|-----|---------|-------------|
| `timeout` | `60` | Seconds to wait for the entity |
| `reload_integration` | `false` | Reload the integration that provides the entity once, before waiting. This skips the back-off of an integration in `setup_retry`, which can otherwise take more than a minute after the device got power |
| `on_timeout` | `abort` | `abort` stops the start and puts the room into `error`; `continue` logs a warning and goes on |

### Activities

| Key | Description |
|-----|-------------|
| `name` | Display name (defaults to the key) |
| `devices` | Devices the activity uses, in power-on order |
| `steps` | Settings applied once the devices are up |
| `on_start` | Home Assistant actions, run alongside the start |
| `on_stop` | Home Assistant actions, run alongside a stop |

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
| `wait_available` | `device` or `entity_id`, `timeout`, `reload_integration`, `on_timeout` | Same as a device's `ready`, for any entity at any point |
| `delay` | `delay_after` | Only wait |

Every service call waits for the device to finish (`blocking`), at most 15 seconds. A failing step is logged and listed in the sensor's `warnings` attribute; the activity continues.

---

## What happens when

### Start

1. **Smart switching** — if another activity runs in the room, its devices that the new one does not use are switched off. Power outlets that are no longer needed are switched off in the background once those devices had their `delay_after_off`.
2. **Power** — all outlets of the activity's devices are switched on at once, so the devices boot in parallel.
3. **`on_start`** starts running alongside.
4. **Devices**, in order: readiness check, switch on (only if off), `delay_after_on` (only if it was switched on).
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

## Entities

One virtual device per room (linked to the area of the same name) with four entities. Entity names and state labels are translated (English and German); the state values themselves are stable keys, so automations work regardless of the language. Entity IDs are generated by Home Assistant from the translated names and may differ per installation — look them up on the room's device page.

### Select — Scene

Shows the running activity and starts, switches or stops activities.

| Option (state value) | Shown as | Meaning |
|----------------------|----------|---------|
| Activity name | Activity name | That activity is active — select another one to switch |
| `idle` | `—` | Idle; selecting it stops the current activity |
| `starting` / `stopping` | `⏳ Starting …` / `⏹ Stopping …` | Transition in progress (read-only) |
| `error` | `⚠ Error` | The last start was aborted (read-only) — see the sensor |

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

With a rocker that sends separate on/off telegrams, use `start_activity` and `stop_activity` instead.

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

---

## License & Support

- License: [MIT](LICENSE)
- Bugs & feature requests: [GitHub Issues](https://github.com/mkshb/hass-av-scenes/issues)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
