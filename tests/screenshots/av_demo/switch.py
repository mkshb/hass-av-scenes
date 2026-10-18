"""Switched power outlets, and the late-night mode of the receiver."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

OUTLETS = {"av_rack": "AV rack outlet", "projector": "Projector outlet"}


async def async_setup_platform(
    hass: HomeAssistant, config: Any, add_entities: AddEntitiesCallback, discovery_info: Any = None
) -> None:
    add_entities([*(Outlet(key, name) for key, name in OUTLETS.items()), LateNight()])


class Outlet(SwitchEntity):
    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_should_poll = False

    def __init__(self, key: str, name: str) -> None:
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}_outlet"

    @property
    def is_on(self) -> bool:
        return self.hass.data[DOMAIN].on[self._key]

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.hass.data[DOMAIN].set(self._key, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.hass.data[DOMAIN].set(self._key, False)
        self.async_write_ha_state()


class LateNight(SwitchEntity):
    """Compresses loud passages, for watching at night."""

    _attr_name = "AV receiver late night"
    _attr_unique_id = f"{DOMAIN}_receiver_late_night"
    _attr_should_poll = False
    _attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
