"""Config entry migration for AV Scenes.

Version history
---------------
1  ``rooms -> activities -> steps`` (or the even older ``device_states``
   format). Every step carries its own ``entity_id`` and a nested
   ``parameters`` dict; ``delay_after`` is also reused while stopping.
2  ``rooms -> devices / activities -> steps``. Power handling, readiness
   checks and the switch-off delay live in reusable device profiles,
   activities list the devices they power on, steps are flat and refer to
   devices by key. Free-form HA actions go into ``on_start`` / ``on_stop``.

The migration only converts data, it never drops any: keys it does not know
are carried over unchanged so that validation can point them out later.
"""
from __future__ import annotations

import copy
import uuid
from typing import Any

from .const import (
    CONF_ACTION,
    CONF_ACTIVITIES,
    CONF_BRIGHTNESS_PCT,
    CONF_COLOR_TEMP_KELVIN,
    CONF_DATA,
    CONF_DELAY_AFTER_OFF,
    CONF_DELAY_AFTER_ON,
    CONF_DEVICE,
    CONF_DEVICES,
    CONF_ENTITY_ID,
    CONF_ID,
    CONF_NAME,
    CONF_ON_START,
    CONF_ON_STOP,
    CONF_POSITION,
    CONF_ROOMS,
    CONF_SOUND_MODE,
    CONF_SOURCE,
    CONF_STEPS,
    CONF_TILT_POSITION,
    CONF_TRANSITION,
    CONF_TYPE,
    CONF_VOLUME_LEVEL,
    STEP_TYPE_CALL_ACTION,
    STEP_TYPE_DELAY,
    STEP_TYPE_POWER_OFF,
    STEP_TYPE_POWER_ON,
    STEP_TYPE_SET_BRIGHTNESS,
    STEP_TYPE_SET_COLOR_TEMP,
    STEP_TYPE_SET_POSITION,
    STEP_TYPE_SET_SOUND_MODE,
    STEP_TYPE_SET_SOURCE,
    STEP_TYPE_SET_TILT,
    STEP_TYPE_SET_VOLUME,
)

# v1 ran these steps without their entity (if any); v2 does not allow one
_STEPS_WITHOUT_DEVICE = (STEP_TYPE_CALL_ACTION, STEP_TYPE_DELAY)

# v1-only keys
_V1_STEP_ID = "step_id"
_V1_STEP_TYPE = "step_type"
_V1_DELAY_AFTER = "delay_after"
_V1_PARAMETERS = "parameters"
_V1_INPUT_SOURCE = "input_source"
_V1_BRIGHTNESS = "brightness"
_V1_COLOR_TEMP = "color_temp"
_V1_SERVICE_DATA = "service_data"
_V1_DEVICE_STATES = "device_states"
_V1_DEVICE_ORDER = "device_order"
_V1_POWER_ON_DELAY = "power_on_delay"
_V1_IS_VOLUME_CONTROLLER = "is_volume_controller"
_V1_DEFAULT_POWER_ON_DELAY = 2

_DELAY_AFTER = "delay_after"


def migrate_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Return a v2 copy of v1 entry data."""
    out = copy.deepcopy(data)
    out[CONF_ROOMS] = {
        room_id: _migrate_room(room)
        for room_id, room in (data.get(CONF_ROOMS) or {}).items()
    }
    return out


def _migrate_room(room: dict[str, Any]) -> dict[str, Any]:
    room_out = {
        key: copy.deepcopy(value)
        for key, value in room.items()
        if key not in (CONF_ACTIVITIES, CONF_DEVICES)
    }
    devices: dict[str, dict[str, Any]] = {}
    entity_to_device: dict[str, str] = {}

    def device_for(entity_id: str) -> str:
        if entity_id in entity_to_device:
            return entity_to_device[entity_id]
        base = entity_id.split(".", 1)[-1] or "device"
        key, n = base, 2
        while key in devices:
            key, n = f"{base}_{n}", n + 1
        devices[key] = {
            CONF_ENTITY_ID: entity_id,
            CONF_DELAY_AFTER_ON: 0,
            CONF_DELAY_AFTER_OFF: 0,
        }
        entity_to_device[entity_id] = key
        return key

    activities_out: dict[str, Any] = {}
    for activity_key, activity in (room.get(CONF_ACTIVITIES) or {}).items():
        activities_out[activity_key] = _migrate_activity(
            activity_key, activity, devices, device_for
        )

    room_out[CONF_DEVICES] = devices
    room_out[CONF_ACTIVITIES] = activities_out
    return room_out


def _migrate_activity(
    activity_key: str,
    activity: dict[str, Any],
    devices: dict[str, dict[str, Any]],
    device_for,
) -> dict[str, Any]:
    steps_v1 = _steps_from_activity(activity)

    managed: list[str] = []        # devices powered on/off by the activity
    touched: list[str] = []        # entities only used by other steps
    stop_delay: dict[str, float] = {}
    steps_out: list[dict[str, Any]] = []

    for step in steps_v1:
        step_type = step.get(_V1_STEP_TYPE)
        entity_id = (step.get(CONF_ENTITY_ID) or "").strip()
        delay = step.get(_V1_DELAY_AFTER) or 0
        device = (
            device_for(entity_id)
            if entity_id and step_type not in _STEPS_WITHOUT_DEVICE
            else None
        )

        if entity_id:
            # v1 waited max(delay_after) per entity while stopping
            stop_delay[entity_id] = max(stop_delay.get(entity_id, 0), delay)
            if entity_id not in touched:
                touched.append(entity_id)

        if step_type == STEP_TYPE_POWER_ON and device:
            if device not in managed:
                managed.append(device)
            profile = devices[device]
            profile[CONF_DELAY_AFTER_ON] = max(profile[CONF_DELAY_AFTER_ON], delay)
            continue

        steps_out.append(_migrate_step(step, device))

    managed_entities = {devices[device][CONF_ENTITY_ID]: device for device in managed}
    for entity_id, delay in stop_delay.items():
        if (device := managed_entities.get(entity_id)) is not None:
            profile = devices[device]
            profile[CONF_DELAY_AFTER_OFF] = max(profile[CONF_DELAY_AFTER_OFF], delay)

    # v1 switched off every entity of the activity while stopping, in reverse
    # order. Entities without a power_on step are not managed in v2, so keep
    # that behaviour as explicit (and editable) on_stop actions.
    on_stop: list[dict[str, Any]] = []
    for entity_id in reversed(touched):
        if entity_id in managed_entities:
            continue
        if entity_id.startswith("cover."):
            on_stop.append(
                {CONF_ACTION: "cover.close_cover", "target": {CONF_ENTITY_ID: entity_id}}
            )
        else:
            on_stop.append(
                {
                    CONF_ACTION: "homeassistant.turn_off",
                    "target": {CONF_ENTITY_ID: entity_id},
                }
            )
        if stop_delay[entity_id] > 0:
            on_stop.append({"delay": {"seconds": stop_delay[entity_id]}})

    activity_out = {
        key: copy.deepcopy(value)
        for key, value in activity.items()
        if key not in (CONF_STEPS, _V1_DEVICE_STATES, _V1_DEVICE_ORDER)
    }
    activity_out.setdefault(CONF_NAME, activity_key)
    activity_out[CONF_DEVICES] = managed
    activity_out[CONF_STEPS] = steps_out
    activity_out.setdefault(CONF_ON_START, [])
    activity_out[CONF_ON_STOP] = list(activity_out.get(CONF_ON_STOP) or []) + on_stop
    return activity_out


def _migrate_step(step: dict[str, Any], device: str | None) -> dict[str, Any]:
    """Flatten a v1 step into the v2 shape."""
    step_type = step.get(_V1_STEP_TYPE)
    params: dict[str, Any] = dict(step.get(_V1_PARAMETERS) or {})
    out: dict[str, Any] = {
        CONF_ID: step.get(_V1_STEP_ID) or str(uuid.uuid4()),
        CONF_TYPE: step_type,
    }
    if device:
        out[CONF_DEVICE] = device

    if step_type == STEP_TYPE_SET_SOURCE:
        _move(params, out, _V1_INPUT_SOURCE, CONF_SOURCE)
    elif step_type == STEP_TYPE_SET_VOLUME:
        _move(params, out, CONF_VOLUME_LEVEL)
    elif step_type == STEP_TYPE_SET_SOUND_MODE:
        _move(params, out, CONF_SOUND_MODE)
    elif step_type in (STEP_TYPE_SET_BRIGHTNESS, STEP_TYPE_SET_COLOR_TEMP):
        if params.get(_V1_BRIGHTNESS) is not None:
            # v1 stored 0-255
            out[CONF_BRIGHTNESS_PCT] = round(params.pop(_V1_BRIGHTNESS) * 100 / 255)
        if params.get(_V1_COLOR_TEMP):
            # v1 stored mireds; light.turn_on no longer accepts color_temp
            out[CONF_COLOR_TEMP_KELVIN] = round(1_000_000 / params.pop(_V1_COLOR_TEMP))
        _move(params, out, CONF_TRANSITION)
    elif step_type == STEP_TYPE_SET_POSITION:
        _move(params, out, CONF_POSITION)
    elif step_type == STEP_TYPE_SET_TILT:
        _move(params, out, CONF_TILT_POSITION)
    elif step_type == STEP_TYPE_CALL_ACTION:
        _move(params, out, CONF_ACTION)
        if params.get(_V1_SERVICE_DATA):
            out[CONF_DATA] = params.pop(_V1_SERVICE_DATA)
        params.pop(_V1_SERVICE_DATA, None)
    elif step_type in (STEP_TYPE_DELAY, STEP_TYPE_POWER_OFF):
        pass

    # Keep anything unexpected rather than losing it
    for key, value in params.items():
        out.setdefault(key, value)

    delay = step.get(_V1_DELAY_AFTER) or 0
    if delay or step_type == STEP_TYPE_DELAY:
        out[_DELAY_AFTER] = delay
    return out


def _move(src: dict[str, Any], dst: dict[str, Any], key: str, new_key: str | None = None) -> None:
    if src.get(key) is not None:
        dst[new_key or key] = src.pop(key)
    else:
        src.pop(key, None)


def _steps_from_activity(activity: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the v1 step list, converting the pre-0.3 device_states format."""
    if CONF_STEPS in activity:
        return list(activity.get(CONF_STEPS) or [])

    device_states: dict[str, Any] = activity.get(_V1_DEVICE_STATES) or {}
    order = activity.get(_V1_DEVICE_ORDER) or list(device_states)
    steps: list[dict[str, Any]] = []

    for entity_id in order:
        config = device_states.get(entity_id)
        if not config:
            continue
        domain = entity_id.split(".")[0]
        delay = config.get(_V1_POWER_ON_DELAY, _V1_DEFAULT_POWER_ON_DELAY)
        steps.append(_v1_step(STEP_TYPE_POWER_ON, entity_id, delay))

        if domain == "media_player":
            if config.get(_V1_INPUT_SOURCE):
                steps.append(
                    _v1_step(STEP_TYPE_SET_SOURCE, entity_id, 0,
                             {_V1_INPUT_SOURCE: config[_V1_INPUT_SOURCE]})
                )
            if config.get(_V1_IS_VOLUME_CONTROLLER):
                steps.append(
                    _v1_step(STEP_TYPE_SET_VOLUME, entity_id, 0,
                             {CONF_VOLUME_LEVEL: config.get(CONF_VOLUME_LEVEL, 0.5)})
                )
        elif domain == "light":
            params = {
                key: config[key]
                for key in (_V1_BRIGHTNESS, _V1_COLOR_TEMP, CONF_TRANSITION)
                if config.get(key) is not None
            }
            if params:
                steps.append(_v1_step(STEP_TYPE_SET_BRIGHTNESS, entity_id, 0, params))
        elif domain == "cover":
            if config.get(CONF_POSITION) is not None:
                steps.append(
                    _v1_step(STEP_TYPE_SET_POSITION, entity_id, 0,
                             {CONF_POSITION: config[CONF_POSITION]})
                )
            if config.get(CONF_TILT_POSITION) is not None:
                steps.append(
                    _v1_step(STEP_TYPE_SET_TILT, entity_id, 0,
                             {CONF_TILT_POSITION: config[CONF_TILT_POSITION]})
                )
    return steps


def _v1_step(
    step_type: str, entity_id: str, delay: float, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        _V1_STEP_ID: str(uuid.uuid4()),
        _V1_STEP_TYPE: step_type,
        CONF_ENTITY_ID: entity_id,
        _V1_DELAY_AFTER: delay,
        _V1_PARAMETERS: params or {},
    }
