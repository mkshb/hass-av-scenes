"""Configuration schema (v2) and validation for AV Scenes.

Layout of ``entry.data``::

    rooms:
      <room_id>:
        name: Wohnzimmer
        devices:
          <device_id>:
            entity_id: media_player.onkyo_receiver
            power_switch: switch.wz_steckdose_multimedia   # optional
            ready: {timeout: 60, reload_integration: true, on_timeout: abort}
            delay_after_power: 0           # boot time after its power switch came on
            delay_after_on: 0
            delay_after_off: 0
            commands:                      # remote buttons -> HA actions
              guide: [...]
        activities:
          <activity_id>:
            name: TV
            icon: mdi:television
            order: 1                       # position in lists (HA stores keys sorted)
            devices: [onkyo, beamer]       # power-on order
            steps: [...]                   # settings once the devices are up
            on_start: [...]                # HA actions
            on_stop: [...]                 # HA actions
            remote:                        # which device gets which buttons
              volume: onkyo
              channels: vu
              transport: vu
              navigation: vu
              buttons: [{command: netflix, name: Netflix, icon: mdi:netflix}]
            commands: {netflix: [...]}     # activity-only commands
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.script import async_validate_actions_config

from .const import (
    COMMAND_GROUPS,
    CONF_ACTION,
    CONF_ACTIVITIES,
    CONF_AREA_ID,
    CONF_BRIGHTNESS_PCT,
    CONF_BUTTONS,
    CONF_COLOR_TEMP_KELVIN,
    CONF_COMMAND,
    CONF_COMMANDS,
    CONF_DATA,
    CONF_DELAY_AFTER_OFF,
    CONF_DELAY_AFTER_ON,
    CONF_DELAY_AFTER_POWER,
    CONF_DEVICE,
    CONF_DEVICES,
    CONF_ENTITY_ID,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    CONF_ON_START,
    CONF_ON_STOP,
    CONF_ON_TIMEOUT,
    CONF_ORDER,
    CONF_POSITION,
    CONF_POWER_SWITCH,
    CONF_READY,
    CONF_RELOAD_INTEGRATION,
    CONF_REMOTE,
    CONF_ROOMS,
    CONF_SOUND_MODE,
    CONF_SOURCE,
    CONF_STATE,
    CONF_STEPS,
    CONF_TARGET,
    CONF_TILT_POSITION,
    CONF_TIMEOUT,
    CONF_TRANSITION,
    CONF_TYPE,
    CONF_VOLUME_LEVEL,
    DEFAULT_READY_TIMEOUT,
    ON_TIMEOUT_ABORT,
    ON_TIMEOUT_OPTIONS,
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
    STEP_TYPE_WAIT_AVAILABLE,
)

CONF_DELAY_AFTER = "delay_after"

_SECONDS = vol.All(vol.Coerce(float), vol.Range(min=0, max=3600))
_PERCENT = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))
_KEY = vol.All(str, vol.Length(min=1))
# Command name -> HA actions; validated in depth by async_validate_config
_COMMANDS = {_KEY: vol.Any(dict, [dict])}

# Wait for these states instead of "not unavailable"
_STATES = vol.All(cv.ensure_list, [cv.string], vol.Length(min=1))

READY_SCHEMA = vol.Schema(
    {
        # Check another entity than the device's own, e.g. the remote of an
        # Apple TV, which is "on" only while the integration is connected
        vol.Optional(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_STATE): _STATES,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_READY_TIMEOUT): vol.All(
            vol.Coerce(float), vol.Range(min=1, max=3600)
        ),
        vol.Optional(CONF_RELOAD_INTEGRATION, default=False): cv.boolean,
        vol.Optional(CONF_ON_TIMEOUT, default=ON_TIMEOUT_ABORT): vol.In(
            ON_TIMEOUT_OPTIONS
        ),
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_POWER_SWITCH): vol.Any(None, cv.entity_id),
        vol.Optional(CONF_READY): vol.Any(None, READY_SCHEMA),
        vol.Optional(CONF_DELAY_AFTER_POWER, default=0): _SECONDS,
        vol.Optional(CONF_DELAY_AFTER_ON, default=0): _SECONDS,
        vol.Optional(CONF_DELAY_AFTER_OFF, default=0): _SECONDS,
        vol.Optional(CONF_COMMANDS, default=dict): _COMMANDS,
    }
)

_STEP_BASE = {
    vol.Optional(CONF_ID): str,
    vol.Required(CONF_TYPE): str,
    vol.Optional(CONF_DELAY_AFTER, default=0): _SECONDS,
}
_DEVICE_STEP = {**_STEP_BASE, vol.Required(CONF_DEVICE): _KEY}

STEP_SCHEMAS: dict[str, vol.Schema] = {
    STEP_TYPE_POWER_ON: vol.Schema(_DEVICE_STEP),
    STEP_TYPE_POWER_OFF: vol.Schema(_DEVICE_STEP),
    STEP_TYPE_SET_SOURCE: vol.Schema({**_DEVICE_STEP, vol.Required(CONF_SOURCE): str}),
    STEP_TYPE_SET_VOLUME: vol.Schema(
        {
            **_DEVICE_STEP,
            vol.Required(CONF_VOLUME_LEVEL): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=1)
            ),
        }
    ),
    STEP_TYPE_SET_SOUND_MODE: vol.Schema(
        {**_DEVICE_STEP, vol.Required(CONF_SOUND_MODE): str}
    ),
    STEP_TYPE_SET_BRIGHTNESS: vol.Schema(
        {
            **_DEVICE_STEP,
            vol.Optional(CONF_BRIGHTNESS_PCT): _PERCENT,
            vol.Optional(CONF_COLOR_TEMP_KELVIN): vol.All(
                vol.Coerce(int), vol.Range(min=1000, max=12000)
            ),
            vol.Optional(CONF_TRANSITION): _SECONDS,
        }
    ),
    STEP_TYPE_SET_COLOR_TEMP: vol.Schema(
        {
            **_DEVICE_STEP,
            vol.Required(CONF_COLOR_TEMP_KELVIN): vol.All(
                vol.Coerce(int), vol.Range(min=1000, max=12000)
            ),
        }
    ),
    STEP_TYPE_SET_POSITION: vol.Schema({**_DEVICE_STEP, vol.Required(CONF_POSITION): _PERCENT}),
    STEP_TYPE_SET_TILT: vol.Schema(
        {**_DEVICE_STEP, vol.Required(CONF_TILT_POSITION): _PERCENT}
    ),
    STEP_TYPE_CALL_ACTION: vol.Schema(
        {
            **_STEP_BASE,
            vol.Required(CONF_ACTION): cv.service,
            vol.Optional(CONF_DATA): dict,
            vol.Optional(CONF_TARGET): dict,
        }
    ),
    STEP_TYPE_DELAY: vol.Schema(_STEP_BASE),
    STEP_TYPE_WAIT_AVAILABLE: vol.All(
        vol.Schema(
            {
                **_STEP_BASE,
                vol.Exclusive(CONF_DEVICE, "target"): _KEY,
                vol.Exclusive(CONF_ENTITY_ID, "target"): cv.entity_id,
                vol.Optional(CONF_STATE): _STATES,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_READY_TIMEOUT): vol.All(
                    vol.Coerce(float), vol.Range(min=1, max=3600)
                ),
                vol.Optional(CONF_RELOAD_INTEGRATION, default=False): cv.boolean,
                vol.Optional(CONF_ON_TIMEOUT, default=ON_TIMEOUT_ABORT): vol.In(
                    ON_TIMEOUT_OPTIONS
                ),
            }
        ),
        cv.has_at_least_one_key(CONF_DEVICE, CONF_ENTITY_ID),
    ),
}


def _step(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise vol.Invalid("step must be a mapping")
    step_type = value.get(CONF_TYPE)
    schema = STEP_SCHEMAS.get(step_type)
    if schema is None:
        raise vol.Invalid(
            f"unknown step type '{step_type}', expected one of: {', '.join(STEP_SCHEMAS)}",
            path=[CONF_TYPE],
        )
    return schema(value)


def _button(value: Any) -> dict[str, Any]:
    """A remote button: a command name, optionally with label and icon."""
    if isinstance(value, str):
        value = {CONF_COMMAND: value}
    return BUTTON_SCHEMA(value)


BUTTON_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND): _KEY,
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(CONF_DEVICE): _KEY,
    }
)

REMOTE_SCHEMA = vol.Schema(
    {
        # A device id, or null to hide the group
        **{vol.Optional(group): vol.Any(None, _KEY) for group in COMMAND_GROUPS},
        vol.Optional(CONF_BUTTONS, default=list): [_button],
    }
)

ACTIVITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(CONF_ORDER): vol.Coerce(int),
        vol.Optional(CONF_DEVICES, default=list): [_KEY],
        vol.Optional(CONF_STEPS, default=list): [_step],
        # Validated in depth by async_validate_config (needs hass)
        vol.Optional(CONF_ON_START, default=list): vol.Any(None, [dict]),
        vol.Optional(CONF_ON_STOP, default=list): vol.Any(None, [dict]),
        vol.Optional(CONF_REMOTE, default=dict): REMOTE_SCHEMA,
        vol.Optional(CONF_COMMANDS, default=dict): _COMMANDS,
    }
)

ROOM_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_AREA_ID): vol.Any(None, str),
        vol.Optional(CONF_DEVICES, default=dict): {_KEY: DEVICE_SCHEMA},
        vol.Optional(CONF_ACTIVITIES, default=dict): {_KEY: ACTIVITY_SCHEMA},
    }
)

CONFIG_SCHEMA = vol.Schema({vol.Optional(CONF_ROOMS, default=dict): {_KEY: ROOM_SCHEMA}})


def _check_references(rooms: dict[str, Any]) -> None:
    """Raise vol.Invalid when an activity or step points to an unknown device."""
    for room_id, room in rooms.items():
        devices = room[CONF_DEVICES]
        for activity_id, activity in room[CONF_ACTIVITIES].items():
            base = [CONF_ROOMS, room_id, CONF_ACTIVITIES, activity_id]
            for idx, device in enumerate(activity[CONF_DEVICES]):
                if device not in devices:
                    raise vol.Invalid(
                        f"unknown device '{device}'", path=[*base, CONF_DEVICES, idx]
                    )
            for idx, step in enumerate(activity[CONF_STEPS]):
                device = step.get(CONF_DEVICE)
                if device is not None and device not in devices:
                    raise vol.Invalid(
                        f"unknown device '{device}'",
                        path=[*base, CONF_STEPS, idx, CONF_DEVICE],
                    )
            remote = activity[CONF_REMOTE]
            for group in COMMAND_GROUPS:
                device = remote.get(group)
                if device is not None and device not in devices:
                    raise vol.Invalid(
                        f"unknown device '{device}'", path=[*base, CONF_REMOTE, group]
                    )
            for idx, button in enumerate(remote[CONF_BUTTONS]):
                device = button.get(CONF_DEVICE)
                if device is not None and device not in devices:
                    raise vol.Invalid(
                        f"unknown device '{device}'",
                        path=[*base, CONF_REMOTE, CONF_BUTTONS, idx, CONF_DEVICE],
                    )


def ordered_activities(activities: dict[str, Any]) -> dict[str, Any]:
    """Activities in display order: by ``order``, then by name.

    Home Assistant stores config entries with sorted keys, so the order the
    activities were written in does not survive a restart.
    """
    return dict(
        sorted(
            activities.items(),
            key=lambda item: (
                item[1].get(CONF_ORDER, 1000),
                str(item[1].get(CONF_NAME) or item[0]).casefold(),
            ),
        )
    )


def validate_config(data: dict[str, Any]) -> dict[str, Any]:
    """Validate v2 data synchronously (schema and cross references)."""
    validated = CONFIG_SCHEMA(data)
    _check_references(validated[CONF_ROOMS])
    for room in validated[CONF_ROOMS].values():
        room[CONF_ACTIVITIES] = ordered_activities(room[CONF_ACTIVITIES])
    return validated


async def _async_validate_actions(
    hass: HomeAssistant, actions: Any, path: list[str | int]
) -> list[dict[str, Any]]:
    try:
        return await async_validate_actions_config(hass, cv.SCRIPT_SCHEMA(actions or []))
    except vol.Invalid as err:
        raise vol.Invalid(err.msg, path=[*path, *err.path]) from err


async def async_validate_config(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate v2 data including the HA actions in hooks and commands."""
    validated = validate_config(data)
    for room_id, room in validated[CONF_ROOMS].items():
        base = [CONF_ROOMS, room_id]
        for device_id, device in room[CONF_DEVICES].items():
            for name, actions in device[CONF_COMMANDS].items():
                device[CONF_COMMANDS][name] = await _async_validate_actions(
                    hass, actions, [*base, CONF_DEVICES, device_id, CONF_COMMANDS, name]
                )
        for activity_id, activity in room[CONF_ACTIVITIES].items():
            path = [*base, CONF_ACTIVITIES, activity_id]
            for key in (CONF_ON_START, CONF_ON_STOP):
                activity[key] = await _async_validate_actions(
                    hass, activity.get(key), [*path, key]
                )
            for name, actions in activity[CONF_COMMANDS].items():
                activity[CONF_COMMANDS][name] = await _async_validate_actions(
                    hass, actions, [*path, CONF_COMMANDS, name]
                )
    return validated


@dataclass(frozen=True, slots=True)
class EntityReference:
    """An entity referenced from the configuration."""

    room_id: str
    path: str
    entity_id: str


def iter_entity_references(data: dict[str, Any]):
    """Yield every entity_id the configuration references directly."""
    for room_id, room in (data.get(CONF_ROOMS) or {}).items():
        for device_id, device in (room.get(CONF_DEVICES) or {}).items():
            base = f"devices.{device_id}"
            if device.get(CONF_ENTITY_ID):
                yield EntityReference(room_id, f"{base}.entity_id", device[CONF_ENTITY_ID])
            if device.get(CONF_POWER_SWITCH):
                yield EntityReference(
                    room_id, f"{base}.power_switch", device[CONF_POWER_SWITCH]
                )
            if (device.get(CONF_READY) or {}).get(CONF_ENTITY_ID):
                yield EntityReference(
                    room_id, f"{base}.ready.entity_id", device[CONF_READY][CONF_ENTITY_ID]
                )
        for activity_id, activity in (room.get(CONF_ACTIVITIES) or {}).items():
            for idx, step in enumerate(activity.get(CONF_STEPS) or []):
                if step.get(CONF_ENTITY_ID):
                    yield EntityReference(
                        room_id,
                        f"activities.{activity_id}.steps[{idx}].entity_id",
                        step[CONF_ENTITY_ID],
                    )


def find_missing_entities(hass: HomeAssistant, data: dict[str, Any]) -> list[EntityReference]:
    """Return references to entities that are neither registered nor have a state.

    A powered-off device that sits in setup_retry keeps its registry entry, so
    it does not count as missing.
    """
    registry = er.async_get(hass)
    return [
        ref
        for ref in iter_entity_references(data)
        if registry.async_get(ref.entity_id) is None
        and hass.states.get(ref.entity_id) is None
    ]
