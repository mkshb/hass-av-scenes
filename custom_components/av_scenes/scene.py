"""Scene platform for AV Scenes integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_ACTIVITIES, DEVICE_NAME_PREFIX
from .coordinator import AVScenesCoordinator
from .model import scene_unique_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AV Scenes scenes from a config entry."""
    coordinator: AVScenesCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    _LOGGER.debug("Setting up scenes, coordinator rooms: %s", coordinator.rooms)
    
    scenes = []
    
    # Create a scene for each activity in each room
    for room_id, room_data in coordinator.rooms.items():
        _LOGGER.debug("Processing room %s: %s", room_id, room_data)
        activities = room_data.get(CONF_ACTIVITIES, {})
        _LOGGER.debug("Room %s has %d activities: %s", room_id, len(activities), list(activities.keys()))
        
        for activity_name in activities.keys():
            scene = AVScene(
                coordinator=coordinator,
                room_id=room_id,
                activity_name=activity_name,
            )
            scenes.append(scene)
            _LOGGER.info("Created scene: %s (ID: %s)", scene.name, scene.unique_id)
    
    async_add_entities(scenes)
    _LOGGER.info(f"Created {len(scenes)} AV scenes total")


class AVScene(Scene):
    """Representation of an AV activity scene.

    Named like the other entities of the room: the room's device name plus
    the activity, e.g. "AV: Wohnzimmer TV". Entity IDs of existing scenes
    stay as they are.
    """

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
        
        self._attr_name = coordinator.activity_name(room_id, activity_name)
        self._attr_unique_id = scene_unique_id(room_id, activity_name)

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene (start the activity)."""
        await self.coordinator.async_start_activity(self.room_id, self.activity_name)

    @property
    def device_info(self):
        """Return device information for grouping."""
        room_name = self.coordinator.rooms[self.room_id].get("name", self.room_id)
        return {
            "identifiers": {(DOMAIN, self.room_id)},
            "name": f"{DEVICE_NAME_PREFIX}: {room_name}",
            "manufacturer": "AV Scenes",
            "model": "Activity Controller",
        }
