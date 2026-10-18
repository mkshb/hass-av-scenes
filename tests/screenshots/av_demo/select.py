"""Display dimmer of the receiver."""
from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant, config: Any, add_entities: AddEntitiesCallback, discovery_info: Any = None
) -> None:
    add_entities([Dimmer()])


class Dimmer(SelectEntity):
    _attr_name = "AV receiver display"
    _attr_unique_id = f"{DOMAIN}_receiver_display"
    _attr_should_poll = False
    _attr_options = ["Bright", "Dim", "Dark", "Off"]
    _attr_current_option = "Dim"

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
