"""Shared helpers for the AV Scenes config/options flow.

Centralises the logic that was previously duplicated across the add-step and
edit-step flows: human-readable step descriptions, parameter parsing and
dynamic schema building (with modern HA selectors).
"""
from __future__ import annotations

import json
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ENTITY_ID,
    CONF_STEP_TYPE,
    CONF_STEP_DELAY_AFTER,
    CONF_STEP_PARAMETERS,
    CONF_INPUT_SOURCE,
    CONF_VOLUME_LEVEL,
    CONF_SOUND_MODE,
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_TRANSITION,
    CONF_POSITION,
    CONF_TILT_POSITION,
    CONF_ACTION,
    CONF_SERVICE_DATA,
    STEP_TYPE_POWER_ON,
    STEP_TYPE_SET_SOURCE,
    STEP_TYPE_SET_VOLUME,
    STEP_TYPE_SET_SOUND_MODE,
    STEP_TYPE_SET_BRIGHTNESS,
    STEP_TYPE_SET_COLOR_TEMP,
    STEP_TYPE_SET_POSITION,
    STEP_TYPE_SET_TILT,
    STEP_TYPE_CALL_ACTION,
    STEP_TYPE_DELAY,
)

# Which entity domains a given step type may target.
_DOMAINS_MEDIA = ["media_player"]
_DOMAINS_LIGHT = ["light"]
_DOMAINS_COVER = ["cover"]
_DOMAINS_ALL = ["media_player", "light", "switch", "cover"]


def step_entity_domains(step_type: str) -> list[str]:
    """Return the entity domains selectable for a given step type."""
    if step_type in (STEP_TYPE_SET_SOURCE, STEP_TYPE_SET_VOLUME, STEP_TYPE_SET_SOUND_MODE):
        return _DOMAINS_MEDIA
    if step_type in (STEP_TYPE_SET_BRIGHTNESS, STEP_TYPE_SET_COLOR_TEMP):
        return _DOMAINS_LIGHT
    if step_type in (STEP_TYPE_SET_POSITION, STEP_TYPE_SET_TILT):
        return _DOMAINS_COVER
    return _DOMAINS_ALL


def _friendly_name(hass: HomeAssistant, entity_id: str, fallback: str = "") -> str:
    """Return an entity's friendly name, falling back to its id (or ``fallback``)."""
    if not entity_id:
        return fallback or entity_id
    state = hass.states.get(entity_id)
    if state is None:
        return entity_id
    return state.attributes.get("friendly_name", entity_id)


def describe_step(hass: HomeAssistant, step: dict[str, Any]) -> str:
    """Return a human-readable one-line description of a step (no leading index)."""
    step_type = step.get(CONF_STEP_TYPE, "unknown")
    entity_id = step.get(CONF_ENTITY_ID, "")
    delay_after = step.get(CONF_STEP_DELAY_AFTER, 0)
    params = step.get(CONF_STEP_PARAMETERS, {})
    name = _friendly_name(hass, entity_id)

    if step_type == STEP_TYPE_POWER_ON:
        desc = f"Turn on {name}"
    elif step_type == STEP_TYPE_SET_SOURCE:
        desc = f"Set {name} source to '{params.get(CONF_INPUT_SOURCE, '')}'"
    elif step_type == STEP_TYPE_SET_VOLUME:
        desc = f"Set {name} volume to {int(params.get(CONF_VOLUME_LEVEL, 0.5) * 100)}%"
    elif step_type == STEP_TYPE_SET_SOUND_MODE:
        desc = f"Set {name} sound mode to '{params.get(CONF_SOUND_MODE, '')}'"
    elif step_type == STEP_TYPE_SET_BRIGHTNESS:
        brightness = params.get(CONF_BRIGHTNESS)
        if brightness is not None:
            desc = f"Set {name} brightness to {int(brightness * 100 / 255)}%"
        else:
            desc = f"Configure {name}"
    elif step_type == STEP_TYPE_SET_COLOR_TEMP:
        desc = f"Set {name} color temp to {params.get(CONF_COLOR_TEMP, 0)} mired"
    elif step_type == STEP_TYPE_SET_POSITION:
        desc = f"Set {name} position to {params.get(CONF_POSITION, 0)}%"
    elif step_type == STEP_TYPE_SET_TILT:
        desc = f"Set {name} tilt to {params.get(CONF_TILT_POSITION, 0)}%"
    elif step_type == STEP_TYPE_CALL_ACTION:
        desc = f"Call action: {params.get(CONF_ACTION, '')}"
    elif step_type == STEP_TYPE_DELAY:
        desc = f"Wait {delay_after} seconds"
    else:
        desc = f"{step_type} on {name}"

    if delay_after > 0 and step_type != STEP_TYPE_DELAY:
        desc += f" (then wait {delay_after}s)"
    return desc


def step_choice_label(hass: HomeAssistant, idx: int, step: dict[str, Any]) -> str:
    """Return a short numbered label for step selection dropdowns."""
    step_type = step.get(CONF_STEP_TYPE, "unknown")
    entity_id = step.get(CONF_ENTITY_ID, "")
    name = _friendly_name(hass, entity_id, fallback="Delay")
    return f"{idx}. {step_type} - {name}"


def translatable_select(options: list[str], translation_key: str) -> SelectSelector:
    """Return a translatable list selector for a fixed set of option keys.

    The visible labels are resolved from ``selector.<translation_key>.options``
    in the translation files, so menu entries follow the HA UI language.
    """
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=opt, label=opt) for opt in options],
            mode=SelectSelectorMode.LIST,
            translation_key=translation_key,
        )
    )


def value_select(values: list[str]) -> SelectSelector:
    """Return a plain dropdown for dynamic values (room/activity names)."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=v, label=v) for v in values],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _num(minimum: int, maximum: int, unit: str | None = None) -> NumberSelector:
    """Return a box NumberSelector for an integer range."""
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement=unit,
        )
    )


def _options_selector(options: list[SelectOptionDict]) -> SelectSelector:
    """Return a dropdown SelectSelector for the given options."""
    return SelectSelector(
        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
    )


def parse_step_params(step_type: str, user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Parse a step-config submission into stored parameters.

    Returns ``(parameters, errors)``. ``errors`` maps a field name to an error
    key from ``translations`` and is empty on success.
    """
    params: dict[str, Any] = {}
    errors: dict[str, str] = {}

    if step_type == STEP_TYPE_SET_SOURCE:
        source = user_input.get(CONF_INPUT_SOURCE)
        if source and source != "none":
            params[CONF_INPUT_SOURCE] = source

    elif step_type == STEP_TYPE_SET_VOLUME:
        params[CONF_VOLUME_LEVEL] = int(user_input.get(CONF_VOLUME_LEVEL, 50)) / 100.0

    elif step_type == STEP_TYPE_SET_SOUND_MODE:
        sound_mode = user_input.get(CONF_SOUND_MODE)
        if sound_mode and sound_mode != "none":
            params[CONF_SOUND_MODE] = sound_mode

    elif step_type == STEP_TYPE_SET_BRIGHTNESS:
        brightness = user_input.get(CONF_BRIGHTNESS)
        if brightness is not None:
            params[CONF_BRIGHTNESS] = int(int(brightness) * 255 / 100)
        color_temp = user_input.get(CONF_COLOR_TEMP)
        if color_temp is not None:
            params[CONF_COLOR_TEMP] = int(color_temp)
        transition = user_input.get(CONF_TRANSITION)
        if transition is not None:
            params[CONF_TRANSITION] = int(transition)

    elif step_type == STEP_TYPE_SET_COLOR_TEMP:
        color_temp = user_input.get(CONF_COLOR_TEMP)
        if color_temp is not None:
            params[CONF_COLOR_TEMP] = int(color_temp)

    elif step_type == STEP_TYPE_SET_POSITION:
        position = user_input.get(CONF_POSITION)
        if position is not None:
            params[CONF_POSITION] = int(position)

    elif step_type == STEP_TYPE_SET_TILT:
        tilt = user_input.get(CONF_TILT_POSITION)
        if tilt is not None:
            params[CONF_TILT_POSITION] = int(tilt)

    elif step_type == STEP_TYPE_CALL_ACTION:
        action = (user_input.get(CONF_ACTION) or "").strip()
        if not action:
            errors[CONF_ACTION] = "invalid_name"
        elif "." not in action:
            errors[CONF_ACTION] = "invalid_action"
        else:
            params[CONF_ACTION] = action

        raw = user_input.get(CONF_SERVICE_DATA)
        if raw:
            try:
                params[CONF_SERVICE_DATA] = json.loads(raw)
            except json.JSONDecodeError:
                errors[CONF_SERVICE_DATA] = "invalid_json"

    return params, errors


def build_step_schema(
    hass: HomeAssistant,
    step_type: str,
    *,
    params: dict[str, Any] | None = None,
    delay: int = 0,
    include_entity: bool = False,
    entity_id: str = "",
) -> vol.Schema:
    """Build the dynamic voluptuous schema for a step's config form.

    Handles both the add flow (``include_entity=False``, empty ``params``) and
    the edit flow (``include_entity=True``, ``params`` pre-filled). Passing the
    existing values as defaults means one code path serves both.
    """
    params = params or {}
    state = hass.states.get(entity_id) if entity_id else None
    schema: dict[Any, Any] = {}

    # Entity selector (edit flow re-selects the target device)
    if include_entity and step_type not in (STEP_TYPE_DELAY, STEP_TYPE_CALL_ACTION):
        from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

        schema[vol.Required(CONF_ENTITY_ID, default=entity_id)] = EntitySelector(
            EntitySelectorConfig(domain=step_entity_domains(step_type))
        )

    # Delay field (delay steps make it the primary, required field)
    if step_type == STEP_TYPE_DELAY:
        schema[vol.Required(CONF_STEP_DELAY_AFTER, default=delay or 1)] = _num(1, 60, "s")
    elif step_type != STEP_TYPE_CALL_ACTION:
        schema[vol.Optional(CONF_STEP_DELAY_AFTER, default=delay)] = _num(0, 60, "s")

    if step_type == STEP_TYPE_POWER_ON:
        pass

    elif step_type == STEP_TYPE_SET_SOURCE:
        current = params.get(CONF_INPUT_SOURCE, "none")
        options = _dynamic_options(state, "source_list", current)
        schema[vol.Required(CONF_INPUT_SOURCE, default=current)] = _options_selector(options)

    elif step_type == STEP_TYPE_SET_VOLUME:
        default_pct = int(params.get(CONF_VOLUME_LEVEL, 0.5) * 100)
        schema[vol.Required(CONF_VOLUME_LEVEL, default=default_pct)] = _num(0, 100, "%")

    elif step_type == STEP_TYPE_SET_SOUND_MODE:
        current = params.get(CONF_SOUND_MODE, "none")
        options = _dynamic_options(state, "sound_mode_list", current)
        schema[vol.Required(CONF_SOUND_MODE, default=current)] = _options_selector(options)

    elif step_type == STEP_TYPE_SET_BRIGHTNESS:
        brightness = params.get(CONF_BRIGHTNESS)
        default_pct = int(brightness * 100 / 255) if brightness is not None else 100
        schema[vol.Optional(CONF_BRIGHTNESS, default=default_pct)] = _num(0, 100, "%")

        color_temp = params.get(CONF_COLOR_TEMP)
        if color_temp is not None:
            schema[vol.Optional(CONF_COLOR_TEMP, default=color_temp)] = _num(153, 500, "mired")
        else:
            schema[vol.Optional(CONF_COLOR_TEMP)] = _num(153, 500, "mired")

        schema[vol.Optional(CONF_TRANSITION, default=params.get(CONF_TRANSITION, 0))] = _num(0, 60, "s")

    elif step_type == STEP_TYPE_SET_COLOR_TEMP:
        schema[vol.Required(CONF_COLOR_TEMP, default=params.get(CONF_COLOR_TEMP, 250))] = _num(153, 500, "mired")

    elif step_type == STEP_TYPE_SET_POSITION:
        schema[vol.Required(CONF_POSITION, default=params.get(CONF_POSITION, 100))] = _num(0, 100, "%")

    elif step_type == STEP_TYPE_SET_TILT:
        schema[vol.Required(CONF_TILT_POSITION, default=params.get(CONF_TILT_POSITION, 50))] = _num(0, 100, "%")

    elif step_type == STEP_TYPE_CALL_ACTION:
        schema[vol.Required(CONF_ACTION, default=params.get(CONF_ACTION, ""))] = str
        current_data = params.get(CONF_SERVICE_DATA, {})
        data_str = json.dumps(current_data) if current_data else ""
        schema[vol.Optional(CONF_SERVICE_DATA, default=data_str)] = str
        schema[vol.Optional(CONF_STEP_DELAY_AFTER, default=delay)] = _num(0, 60, "s")

    return vol.Schema(schema)


def _dynamic_options(state: Any, attr: str, current: str) -> list[SelectOptionDict]:
    """Build dropdown options from a media_player list attribute.

    Always includes a ``none`` sentinel and re-adds ``current`` if it is no
    longer offered by the device (so an edit form never loses the saved value).
    """
    values = state.attributes.get(attr, []) if state else []
    options: list[SelectOptionDict] = [SelectOptionDict(value="none", label="—")]
    for value in values:
        options.append(SelectOptionDict(value=value, label=value))
    if current and current != "none" and current not in values:
        options.append(SelectOptionDict(value=current, label=f"{current} (current)"))
    return options
