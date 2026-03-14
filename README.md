# AV Scenes — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/mkshb/ha_av_scenes.svg)](https://github.com/mkshb/ha_av_scenes/releases)
[![License](https://img.shields.io/github/license/mkshb/ha_av_scenes.svg)](LICENSE)

Activity-based AV control for Home Assistant — an open-source alternative to Logitech Harmony and Roomie Remote.

---

## Overview

AV Scenes lets you control groups of devices (AV receivers, projectors, TVs, lights, outlets, covers) through named activities. Each activity executes a sequence of steps in order, with optional delays between them. When switching activities, devices that are no longer needed are turned off automatically; devices shared between activities stay on and are simply reconfigured.

Everything is configured through the Home Assistant UI — no YAML required.

---

## Features

| Feature | Description |
|---------|-------------|
| Multi-room | Independent activity management per room |
| 11 step types | Power on/off, source, volume, sound mode, brightness, color temp, position, tilt, delay, any HA action |
| Smart activity switching | Devices no longer needed in the new activity are turned off automatically |
| Ordered shutdown | When an activity stops, devices are powered off in reverse start order, respecting the original `delay_after` values |
| Flexible delays | Configurable wait time (0–60 s) after each step |
| Race condition protection | Concurrent calls for the same room are serialized |
| 4 entity platforms | Scene, Switch, Sensor, Select — one virtual HA device per room |
| Areas integration | Each virtual device links automatically to the matching HA Area |
| UI configuration | Full setup via the config flow and options flow |
| Persistence | Configuration survives HA restarts |

---

## Supported Entity Types

| Type | Domain | Controllable parameters |
|------|--------|------------------------|
| AV Receiver, Projector, TV, Media Player | `media_player.*` | On/off, input source, volume, sound mode |
| Lights | `light.*` | On/off, brightness, color temperature, transition |
| Outlets / Switches | `switch.*` | On/off |
| Covers (blinds, shutters) | `cover.*` | Open/close, position, tilt |
| Any HA entity | — | Via `call_action` step |

---

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. **Integrations** → three dots top right → **Custom repositories**
3. Add repository:
   - **Repository:** `https://github.com/mkshb/ha_av_scenes`
   - **Category:** Integration
4. Find "AV Scenes" in the list and click **Download**
5. Restart Home Assistant

### Manual

1. Download the latest release from [Releases](https://github.com/mkshb/ha_av_scenes/releases)
2. Copy the `custom_components/av_scenes` folder into your `config/custom_components/` directory
3. Restart Home Assistant

---

## Setup

1. **Settings** → **Devices & Services** → **+ Add Integration**
2. Search for **AV Scenes** and select it
3. Click **Configure** to open the options flow

### Add a Room

1. Choose an existing Home Assistant Area **or** enter a custom room name
2. Confirm — the room appears in the list immediately and a virtual device is created in the matching Area

### Create an Activity

1. Select a room → **Manage activities** → **Add new activity**
2. Enter a name (e.g., "Watch Movie")
3. Add steps one by one — the wizard guides you through each step type

### Step Types

| Step type | Applicable device | Configurable parameters |
|-----------|------------------|------------------------|
| **Turn on device** | Any | — |
| **Turn off device** | Any | — |
| **Set input source** | `media_player` | Source from the device's source list |
| **Set volume** | `media_player` | Volume 0–100 % |
| **Set sound mode** | `media_player` | Sound mode from the device's mode list |
| **Set brightness / color** | `light` | Brightness 0–100 %, color temperature (Mired), transition time |
| **Set color temperature** | `light` | Color temperature 153–500 Mired |
| **Set position** | `cover` | Position 0–100 % |
| **Set tilt** | `cover` | Tilt 0–100 % |
| **Call action** | Any | HA action (`domain.action`), optional JSON service data |
| **Wait / Delay** | — | Fixed delay 1–60 seconds |

Every step except *Wait / Delay* accepts an optional **delay_after** (0–60 s) that is waited after the step executes.

After creating an activity you can **edit**, **delete**, **reorder**, **copy**, or **rename** both steps and activities at any time.

---

## Entities

For each configured room, AV Scenes creates one virtual HA device (linked to the matching Area) with four entities:

### Select — `select.<room>_szene`

The primary control entity, visible in the HA Area dashboard under **Other**.

| Displayed option | Meaning |
|-----------------|---------|
| Activity name (e.g., "Watch Movie") | That activity is active — select a different one to switch |
| `—` | Idle — no activity running; selecting this stops the current activity |
| `⏳ Startet …` | Activity is starting (read-only, cannot be selected) |
| `⏹ Stoppt …` | Activity is stopping (read-only, cannot be selected) |

Selecting an activity name starts it. Selecting `—` stops the current activity.

### Sensor — `sensor.<room>_aktivitat`

Reports the current activity lifecycle state with step-level progress.

**State values:** `idle` · `starting` · `active` · `stopping`

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `activity_name` | `str \| null` | Name of the active activity, or `null` when idle |
| `available_activities` | `list[str]` | All configured activity names for this room |
| `current_step` | `int` | Index of the step currently executing (0 when idle) |
| `total_steps` | `int` | Total number of steps in the active activity |
| `step_progress_pct` | `int` | Execution progress 0–100 % |
| `steps` | `list` | Step summary (nr, type, entity, delay_after) — only present while an activity is active |

### Switch — `switch.<room>_activity`

Binary on/off showing whether an activity is running.

- `on` → an activity is active or transitioning
- `off` → idle
- `turn_off` → stops the current activity

**Attributes:** `current_activity`, `available_activities`

### Scene — `scene.<room>_<activity_name>`

One HA scene entity per configured activity. Activating a scene starts the corresponding activity.

```yaml
action: scene.turn_on
target:
  entity_id: scene.living_room_watch_movie
```

---

## Services

```yaml
# Start an activity
action: av_scenes.start_activity
data:
  room: living_room   # internal room ID
  activity: watch_movie

# Stop the current activity (turns off all devices in reverse order)
action: av_scenes.stop_activity
data:
  room: living_room

# Reload configuration without restarting HA
action: av_scenes.reload
```

> **Room ID:** lowercase version of the room name, spaces replaced with `_`. The exact ID is shown in the room list in the options flow.

---

## Shutdown Sequence

When an activity stops (either manually or because a new activity is starting), devices are powered off in the **reverse of the start order**. The `delay_after` value of each device's last step is respected, so dependent devices (e.g., an outlet that powers a TV) are turned off in the correct order with the correct timing.

**Example** — start order and delays:

| # | Device | delay_after |
|---|--------|-------------|
| 1 | Outlet | 5 s |
| 2 | TV | 3 s |
| 3 | Apple TV | 0 s |

**Shutdown order:**

1. Turn off Apple TV → wait 0 s
2. Turn off TV → wait 3 s
3. Turn off Outlet → wait 0 s

---

## Example Scenarios

### Movie Night

1. Turn on receiver (`delay_after: 3 s`)
2. Turn on projector (`delay_after: 10 s`)
3. Turn on Blu-ray player (`delay_after: 2 s`)
4. Set receiver input to BD/DVD (`delay_after: 1 s`)
5. Set receiver volume to 65 %
6. Set cover to 0 % (closed)
7. Dim light to 5 % brightness

### Smart Activity Switching — Apple TV → Sonos

**Running activity "Apple TV"** uses: Projector, Receiver, Apple TV
**New activity "Sonos"** uses: Receiver, Sonos

What AV Scenes does automatically:
- Projector is **turned off** (not needed in Sonos)
- Apple TV is **turned off** (not needed in Sonos)
- Receiver **stays on** — input and volume are updated in place
- Sonos is **turned on**

Result: switch completes in 2–3 seconds instead of 20–30 seconds.

### Dependent Devices (Outlet Before TV)

1. Turn on outlet (`delay_after: 5 s`) — TV now has power
2. Set cover to 60 % (`delay_after: 1 s`)
3. Dim light to 8 % (`delay_after: 1 s`)
4. Turn on TV (`delay_after: 3 s`) — boots correctly
5. Set TV input to HDMI 1 (`delay_after: 1 s`)
6. Turn on Apple TV

---

## Lovelace Examples

### Area Dashboard

Because all entities belong to a virtual device with `suggested_area` set to the room name, they appear automatically in the HA Area dashboard. The **Select** entity shows up under **Other** and can be used to start, switch, and stop activities directly from the area card.

### Entities Card

```yaml
type: entities
title: Living Room
entities:
  - entity: select.living_room_szene
    name: Activity
  - entity: switch.living_room_activity
    name: Status
  - entity: sensor.living_room_aktivitat
    name: State
```

### Progress Card (Markdown)

```yaml
type: markdown
content: |
  ## Living Room
  **State:** {{ states('sensor.living_room_aktivitat') }}
  {% set act = state_attr('sensor.living_room_aktivitat', 'activity_name') %}
  {% if act %}
  **Activity:** {{ act }}
  **Progress:** {{ state_attr('sensor.living_room_aktivitat', 'step_progress_pct') }} %
  (step {{ state_attr('sensor.living_room_aktivitat', 'current_step') }}
  of {{ state_attr('sensor.living_room_aktivitat', 'total_steps') }})
  {% endif %}
```

### Automation — Start Activity at a Fixed Time

```yaml
automation:
  - alias: "Movie night at 8 PM"
    trigger:
      - platform: time
        at: "20:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.someone_home
        state: "on"
    action:
      - action: av_scenes.start_activity
        data:
          room: living_room
          activity: watch_movie
```

---

## Known Limitations

- Input source selection requires the `source_list` attribute on the `media_player` entity
- Sound mode selection requires the `sound_mode_list` attribute on the `media_player` entity
- Cover tilt control requires the `cover.set_cover_tilt_position` service to be available

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## License & Support

- License: [MIT](LICENSE)
- Bugs & feature requests: [GitHub Issues](https://github.com/mkshb/ha_av_scenes/issues)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
