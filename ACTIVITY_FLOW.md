# Activity Flow

What AV Scenes switches when, and how. The diagrams follow the engine in `coordinator.py`; the configuration keys are described in the [README](README.md#configuration).

- [Commands](#commands) – what happens when a start or stop arrives
- [Room states](#room-states) – idle, starting, active, stopping, error
- [Start](#start) – smart switching, power, devices, steps, `on_start`
- [Bringing up a device](#bringing-up-a-device) – boot time, readiness check, switching on
- [Stop](#stop) – devices off, cool-down, power outlets, `on_stop`
- [How devices are switched](#how-devices-are-switched) – which action for which entity
- [Example](#example) – the living room from the README, step by step

## Commands

Every way to start or stop an activity ends up here: the scene, the room's switch and select, the card, and the actions `start_activity`, `stop_activity` and `toggle_activity`. Commands for one room run one at a time; the last one wins.

```mermaid
flowchart TD
    cmd(["Command for a room"]) --> toggle{"toggle_activity?"}
    toggle -- "yes, an activity runs or failed<br/>(and is not stopping)" --> stopcmd["Stop"]
    toggle -- "yes, nothing runs" --> pick["Start the given activity, else<br/>default_activity, else the last used,<br/>else the first in order"]
    toggle -- no --> same
    stopcmd --> same
    pick --> same{"Same command<br/>already running?"}
    same -- yes --> join(["Wait for it,<br/>nothing new runs"])
    same -- no --> cancel["Cancel what runs in the room<br/>(a start or a stop)"]
    cancel --> newer{"Another command arrived<br/>while this one waited?"}
    newer -- yes --> drop(["Dropped, the newer one runs"])
    newer -- no --> kind{"Start or stop?"}
    kind -- start --> runstart(["Start"])
    kind -- stop --> runstop(["Stop"])
```

A cancelled start or stop ends where it is: nothing is undone, its `on_start` or `on_stop` actions are cancelled, and the new command takes over from that state. A stop after a cancelled or failed start switches off what was already powered.

## Room states

The state is the room's sensor; the switch is on in every state but `idle`.

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> starting: start
    starting --> active: devices up, steps done, on_start done
    starting --> error: readiness check aborts, or a failure
    starting --> starting: start of another activity
    starting --> stopping: stop
    active --> starting: start of another activity (smart switching)
    active --> stopping: stop
    error --> starting: start
    error --> stopping: stop
    stopping --> idle: devices off, on_stop done
    stopping --> error: failure
    stopping --> starting: start
```

After a Home Assistant restart, `active` and `error` are restored; a room that was `starting` or `stopping` comes back as `error` ("Interrupted by a Home Assistant restart"), so a stop cleans up.

## Start

```mermaid
flowchart TD
    s0(["Start an activity"]) --> s1["Room: starting<br/>progress 0 of devices + steps,<br/>warnings and error cleared"]
    s1 --> s2["Cancel pending power cuts<br/>of the outlets this activity needs"]
    s2 --> s3{"Was another activity<br/>running in the room?"}
    s3 -- yes --> sw1["Smart switching: switch off the devices<br/>the new activity does not use,<br/>last one first"]
    sw1 --> sw2["Their outlets that neither the new activity<br/>nor a running activity of another room needs:<br/>cut in the background after the<br/>longest delay_after_off of their devices"]
    sw2 --> p1
    s3 -- no --> p1{"Do the devices have<br/>power outlets?"}
    p1 -- yes --> p2["homeassistant.turn_on for all outlets<br/>in one call, so the devices boot in parallel;<br/>remember which outlets were off"]
    p1 -- no --> h1
    p2 --> h1["on_start starts, in parallel<br/>(Home Assistant script engine)"]
    h1 --> d1["Bring up each device of the activity,<br/>in the order of devices<br/>(see next diagram)"]
    d1 --> st1["Steps, in order:<br/>run the step, then wait its delay_after"]
    st1 --> h2["Wait until on_start is done"]
    h2 --> ok(["Room: active<br/>remembered as the last used activity"])

    d1 -. "readiness check with on_timeout: abort,<br/>or an unexpected failure" .-> err
    st1 -. "wait_available with on_timeout: abort,<br/>or an unexpected failure" .-> err
    err(["Room: error<br/>on_start cancelled,<br/>reason in the sensor and in Repairs"])
```

Steps run once all devices are up:

| Step | Action |
|------|--------|
| `set_source` | `media_player.select_source` |
| `set_volume` | `media_player.volume_set` |
| `set_sound_mode` | `media_player.select_sound_mode` |
| `set_brightness`, `set_color_temp` | `light.turn_on` |
| `set_position`, `set_tilt` | `cover.set_cover_position`, `cover.set_cover_tilt_position` |
| `power_on`, `power_off` | as in [How devices are switched](#how-devices-are-switched) |
| `call_action` | the given action with its `data` and `target` |
| `wait_available` | a readiness check at this point, see below |
| `delay` | nothing, only its `delay_after` |

A step that fails or takes longer than 15 seconds is listed in the sensor's `warnings`; the start goes on.

## Bringing up a device

For every device of the activity, in the order of `devices`:

```mermaid
flowchart TD
    d0(["Next device"]) --> d1{"Was its outlet just<br/>switched on by this start?"}
    d1 -- "yes, with delay_after_power" --> d2["Boot time: wait delay_after_power,<br/>counted from switching the outlets on,<br/>so devices on one outlet boot together"]
    d1 -- no --> r0
    d2 --> r0{"ready configured?"}
    r0 -- no --> o1
    r0 -- yes --> r1{"Outlet just switched on<br/>and reload_integration?"}
    r1 -- yes --> r2["Reload the integration of the checked entity<br/>and wait for the reload: it last saw the<br/>device without power and may still say off"]
    r1 -- no --> r3
    r2 --> r3{"Ready?<br/>ready.entity_id, else the device:<br/>one of ready.state,<br/>else anything but unavailable"}
    r3 -- yes --> o1
    r3 -- no --> r4["With reload_integration (not done yet):<br/>reload the integration, again every 5 s<br/>while it is in setup_retry.<br/>Wait for the state, at most ready.timeout"]
    r4 -- ready --> o1
    r4 -- "timeout,<br/>on_timeout: continue" --> o1
    r4 -- "timeout,<br/>on_timeout: abort" --> err(["Start aborted:<br/>room error"])
    o1{"Is the device off?<br/>off, standby, unavailable,<br/>unknown, closed, or missing"}
    o1 -- no --> devdone
    o1 -- yes --> o2["Switch it on<br/>(see How devices are switched)"]
    o2 --> o3["Wait delay_after_on"]
    o3 --> devdone(["Progress + 1"])
```

A `wait_available` step runs the same check as `ready`, at any point of the steps, for a device or any entity.

## Stop

```mermaid
flowchart TD
    t0(["Stop"]) --> t1{"Does an activity run<br/>(or did it fail) in the room?"}
    t1 -- no --> t0n(["Nothing to do"])
    t1 -- yes --> t2["Room: stopping<br/>on_stop starts, in parallel"]
    t2 --> t3["Devices of the activity,<br/>in reverse order"]
    t3 --> t4{"Is the device<br/>already off?"}
    t4 -- no --> t5["Switch it off<br/>cool-down: delay_after_off"]
    t4 -- yes --> t6["No call<br/>cool-down: what is left of its<br/>delay_after_off since it went off"]
    t5 --> t7["Per outlet: the longest<br/>cool-down of its devices"]
    t6 --> t7
    t7 --> t8{"Outlet used by a running activity<br/>of another room?"}
    t8 -- yes --> keep["Stays on"]
    t8 -- no --> t9{"Cool-down left?"}
    t9 -- no --> now["homeassistant.turn_off at once,<br/>all such outlets in one call"]
    t9 -- yes --> later["Cut in the background<br/>after the cool-down"]
    keep --> t10
    now --> t10
    later --> t10["Wait until on_stop is done"]
    t10 --> t11(["Room: idle"])

    later -. "when the cool-down is over" .-> cut{"Needed again by a start<br/>of this room or a running<br/>activity of another room?"}
    cut -- yes --> cutkeep(["Stays on"])
    cut -- no --> cutoff(["homeassistant.turn_off"])
```

The room does not wait for the cool-down: it is `idle` as soon as its devices are off and `on_stop` is done, so the status LED of a wall button goes out at once. `on_stop` runs on a full stop only, not when smart switching to another activity.

## How devices are switched

| Device | Switch on | Switch off |
|--------|-----------|------------|
| Power outlet (`power_switch`) | `homeassistant.turn_on`, all outlets of the activity in one call | `homeassistant.turn_off` |
| Cover | `cover.open_cover` | `cover.close_cover` |
| Media player that cannot be switched (no turn on / turn off support, e.g. a Sonos speaker) | skipped | skipped |
| Device its integration reports as unreachable | skipped, with a warning | `homeassistant.turn_off` |
| Any other entity | `homeassistant.turn_on` | `homeassistant.turn_off` |

Every call waits for the device (`blocking`), at most 15 seconds. A call that fails or takes longer is logged and listed in the sensor's `warnings`; the activity goes on. A device that is already on gets no turn-on and no `delay_after_on`.

## Example

The living room from the [README](README.md#configuration): Onkyo receiver and VU+ on the multimedia outlet, the projector on its own outlet with 180 s cool-down, every device with a readiness check that reloads its integration.

### Starting TV from idle

```mermaid
sequenceDiagram
    autonumber
    participant AV as AV Scenes
    participant P as Outlets
    participant O as Onkyo
    participant B as Projector
    participant V as VU+
    participant H as on_start
    Note over AV: Room: starting (0 of 6)
    AV->>P: homeassistant.turn_on multimedia and projector outlet
    AV-)H: on_start: covers closed if bright, ambient light 15 %
    AV->>O: reload Onkyo integration, wait until available (60 s, abort)
    AV->>O: homeassistant.turn_on (if off)
    AV->>B: reload Epson integration, wait until available (60 s, continue)
    AV->>B: homeassistant.turn_on (if off)
    AV->>V: reload VU+ integration, wait until available (60 s, continue)
    AV->>V: homeassistant.turn_on (if off)
    AV->>O: media_player.select_source SAT
    AV->>O: media_player.select_sound_mode THX
    AV->>O: media_player.volume_set 0.35
    H--)AV: on_start done
    Note over AV: Room: active (6 of 6)
```

If the Onkyo does not become available within 60 s, the start ends in `error` after step 3; with `continue` (projector, VU+) it only logs a warning and goes on.

### Switching from TV to Musik

```mermaid
sequenceDiagram
    autonumber
    participant AV as AV Scenes
    participant P as Outlets
    participant O as Onkyo
    participant B as Projector
    participant V as VU+
    Note over AV: Room: starting
    AV->>V: homeassistant.turn_off (not used by Musik)
    AV->>B: homeassistant.turn_off (not used by Musik)
    AV->>P: homeassistant.turn_on multimedia outlet (already on, stays on)
    Note over O: already on: no reload wait, no turn_on
    AV->>O: media_player.select_source NET
    Note over AV: Room: active
    Note over P: 180 s later, in the background
    AV->>P: homeassistant.turn_off projector outlet
```

`on_stop` of TV does not run, the covers stay as they are.

### Stopping TV

```mermaid
sequenceDiagram
    autonumber
    participant AV as AV Scenes
    participant P as Outlets
    participant O as Onkyo
    participant B as Projector
    participant V as VU+
    participant H as on_stop
    Note over AV: Room: stopping
    AV-)H: on_stop: open the covers
    AV->>V: homeassistant.turn_off
    AV->>B: homeassistant.turn_off
    AV->>O: homeassistant.turn_off
    AV->>P: homeassistant.turn_off multimedia outlet (no cool-down)
    H--)AV: on_stop done
    Note over AV: Room: idle
    Note over P: 180 s later, in the background
    AV->>P: homeassistant.turn_off projector outlet
```
