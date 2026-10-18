"""Blinds that open and close at once."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant, config: Any, add_entities: AddEntitiesCallback, discovery_info: Any = None
) -> None:
    add_entities([Blinds()])


class Blinds(CoverEntity):
    _attr_name = "Living room blinds"
    _attr_unique_id = f"{DOMAIN}_blinds"
    _attr_should_poll = False
    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_is_closed = False

    async def async_open_cover(self, **kwargs: Any) -> None:
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        self._attr_is_closed = True
        self.async_write_ha_state()
