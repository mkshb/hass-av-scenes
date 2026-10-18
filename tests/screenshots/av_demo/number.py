"""Tone and speaker levels of the receiver, as its own app offers them."""
from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

# key -> name, minimum, maximum, value
LEVELS = {
    "treble": ("AV receiver treble", -10, 10, 2),
    "bass": ("AV receiver bass", -10, 10, -3),
    "center": ("AV receiver center level", -12, 12, -2),
    "subwoofer": ("AV receiver subwoofer level", -15, 12, 4),
}


async def async_setup_platform(
    hass: HomeAssistant, config: Any, add_entities: AddEntitiesCallback, discovery_info: Any = None
) -> None:
    add_entities(Level(key, *spec) for key, spec in LEVELS.items())


class Level(NumberEntity):
    _attr_should_poll = False
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1

    def __init__(self, key: str, name: str, low: int, high: int, value: int) -> None:
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_receiver_{key}"
        self._attr_native_min_value = low
        self._attr_native_max_value = high
        self._attr_native_value = value

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
