"""Remotes of the Apple TV and the satellite receiver; on while connected."""
from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant, config: Any, add_entities: AddEntitiesCallback, discovery_info: Any = None
) -> None:
    add_entities([DemoRemote("apple_tv", "Apple TV"), DemoRemote("satellite_receiver", "Satellite receiver")])


class DemoRemote(RemoteEntity):
    _attr_should_poll = False
    _attr_is_on = True

    def __init__(self, key: str, name: str) -> None:
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}_remote"

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        _LOGGER.info("%s: %s", self.name, list(command))
