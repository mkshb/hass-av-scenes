"""Switch platform for AV Scenes integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_ACTIVITIES,
    ATTR_CURRENT_ACTIVITY,
    ATTR_AVAILABLE_ACTIVITIES,
)
from .coordinator import AVScenesConfigEntry, AVScenesCoordinator
from .entity import AVRoomEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AVScenesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AV Scenes switches from a config entry."""
    coordinator = entry.runtime_data

    switches = [
        RoomActivitySwitch(coordinator, room_id)
        for room_id in coordinator.rooms
    ]
    async_add_entities(switches)
    _LOGGER.debug("Created %d room activity switches", len(switches))


class RoomActivitySwitch(AVRoomEntity, SwitchEntity):
    """Representation of a room activity status."""

    _attr_translation_key = "activity_switch"

    def __init__(
        self,
        coordinator: AVScenesCoordinator,
        room_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, room_id)
        self._attr_unique_id = f"{DOMAIN}_activity_{room_id}"

    @property
    def is_on(self) -> bool:
        """Return true if an activity is running."""
        return self.room_id in self.coordinator.active_activities

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        room_data = self.coordinator.rooms.get(self.room_id, {})
        activities = room_data.get(CONF_ACTIVITIES, {})

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
