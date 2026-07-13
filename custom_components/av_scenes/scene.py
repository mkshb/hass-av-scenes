"""Scene platform for AV Scenes integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_ACTIVITIES
from .coordinator import AVScenesConfigEntry, AVScenesCoordinator
from .entity import room_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AVScenesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AV Scenes scenes from a config entry."""
    coordinator = entry.runtime_data

    scenes = [
        AVScene(coordinator, room_id, activity_name)
        for room_id, room_data in coordinator.rooms.items()
        for activity_name in room_data.get(CONF_ACTIVITIES, {})
    ]
    async_add_entities(scenes)
    _LOGGER.debug("Created %d AV scenes total", len(scenes))


class AVScene(Scene):
    """Representation of an AV activity scene."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AVScenesCoordinator,
        room_id: str,
        activity_name: str,
    ) -> None:
        """Initialize the scene."""
        self.coordinator = coordinator
        self.room_id = room_id
        self.activity_name = activity_name

        self._room_name = coordinator.rooms[room_id].get("name", room_id)
        self._attr_name = activity_name
        self._attr_unique_id = f"{DOMAIN}_{room_id}_{activity_name}"

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene (start the activity)."""
        await self.coordinator.async_start_activity(self.room_id, self.activity_name)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for grouping."""
        return room_device_info(self.room_id, self._room_name)
