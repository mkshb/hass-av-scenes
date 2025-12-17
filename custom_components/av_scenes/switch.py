"""Switch platform for AV Scenes integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ACTIVITY_STATE_ACTIVE,
    ATTR_CURRENT_ACTIVITY,
    ATTR_AVAILABLE_ACTIVITIES,
)
from .coordinator import AVScenesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AV Scenes switches from a config entry."""
    coordinator: AVScenesCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    switches = []
    
    # Create a switch for each room to show activity status
    for room_id in coordinator.rooms.keys():
        switches.append(RoomActivitySwitch(coordinator, room_id))
    
    async_add_entities(switches)
    _LOGGER.info(f"Created {len(switches)} room activity switches")


class RoomActivitySwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a room activity status."""

    def __init__(
        self,
        coordinator: AVScenesCoordinator,
        room_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.room_id = room_id
        
        room_name = coordinator.rooms[room_id].get("name", room_id)
        self._attr_name = f"{room_name} Activity"
        self._attr_unique_id = f"{DOMAIN}_activity_{room_id}"

    @property
    def is_on(self) -> bool:
        """Return true if an activity is running."""
        return self.room_id in self.coordinator.active_activities

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        room_data = self.coordinator.rooms.get(self.room_id, {})
        activities = room_data.get("activities", {})
        
        attrs = {
            ATTR_AVAILABLE_ACTIVITIES: list(activities.keys()),
        }
        
        if self.room_id in self.coordinator.active_activities:
            attrs[ATTR_CURRENT_ACTIVITY] = self.coordinator.active_activities[self.room_id]
        
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on is not supported - use scenes to start activities."""
        _LOGGER.warning(
            "Cannot turn on activity switch directly. Use a scene to start an activity."
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the current activity."""
        await self.coordinator.async_stop_activity(self.room_id)

    @property
    def device_info(self):
        """Return device information for grouping."""
        room_name = self.coordinator.rooms[self.room_id].get("name", self.room_id)
        return {
            "identifiers": {(DOMAIN, self.room_id)},
            "name": f"AV Room: {room_name}",
            "manufacturer": "AV Scenes",
            "model": "Activity Controller",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
