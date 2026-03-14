"""Select platform for AV Scenes integration.

Provides one SelectEntity per room that:
 - shows the active activity name (or a status label during transitions)
 - lets the user start an activity by selecting its name
 - lets the user stop the current activity by selecting "—"
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_ACTIVITIES,
    DEVICE_NAME_PREFIX,
    ACTIVITY_STATE_IDLE,
    ACTIVITY_STATE_STARTING,
    ACTIVITY_STATE_STOPPING,
)
from .coordinator import AVScenesCoordinator

_LOGGER = logging.getLogger(__name__)

# Fixed option labels for transitional states and idle
_OPT_IDLE = "—"
_OPT_STARTING = "⏳ Startet …"
_OPT_STOPPING = "⏹ Stoppt …"

# Options the user must not be able to actively choose
_READONLY_OPTIONS = {_OPT_STARTING, _OPT_STOPPING}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AV Scenes select entities from a config entry."""
    coordinator: AVScenesCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        RoomActivitySelect(coordinator, room_id)
        for room_id in coordinator.rooms
    ]
    async_add_entities(entities)
    _LOGGER.debug("Created %d room activity selects", len(entities))


class RoomActivitySelect(CoordinatorEntity, SelectEntity):
    """Select entity that shows the current activity and allows switching."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:play-circle-outline"

    def __init__(self, coordinator: AVScenesCoordinator, room_id: str) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.room_id = room_id

        room_data = coordinator.rooms[room_id]
        self._room_name: str = room_data.get("name", room_id)
        self._attr_name = "Szene"
        self._attr_unique_id = f"{DOMAIN}_select_{room_id}"

    # ------------------------------------------------------------------
    # Options — activity names + idle; transitional states added live
    # ------------------------------------------------------------------

    @property
    def options(self) -> list[str]:
        """Return all selectable options plus any active status label."""
        activities = list(
            self.coordinator.rooms.get(self.room_id, {})
            .get(CONF_ACTIVITIES, {})
            .keys()
        )
        base = [_OPT_IDLE] + activities

        state = self.coordinator.activity_states.get(self.room_id, ACTIVITY_STATE_IDLE)
        if state == ACTIVITY_STATE_STARTING:
            return [_OPT_STARTING] + base
        if state == ACTIVITY_STATE_STOPPING:
            return [_OPT_STOPPING] + base
        return base

    # ------------------------------------------------------------------
    # Current value
    # ------------------------------------------------------------------

    @property
    def current_option(self) -> str:
        """Return the currently displayed option."""
        state = self.coordinator.activity_states.get(self.room_id, ACTIVITY_STATE_IDLE)

        if state == ACTIVITY_STATE_STARTING:
            return _OPT_STARTING
        if state == ACTIVITY_STATE_STOPPING:
            return _OPT_STOPPING

        activity = self.coordinator.active_activities.get(self.room_id)
        return activity if activity else _OPT_IDLE

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    async def async_select_option(self, option: str) -> None:
        """Handle user selection."""
        if option in _READONLY_OPTIONS:
            # Transitional states must not be actively selected
            _LOGGER.debug("Ignoring selection of read-only option '%s'", option)
            return

        if option == _OPT_IDLE:
            await self.coordinator.async_stop_activity(self.room_id)
        else:
            await self.coordinator.async_start_activity(self.room_id, option)

    # ------------------------------------------------------------------
    # Device
    # ------------------------------------------------------------------

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.room_id)},
            "name": f"{DEVICE_NAME_PREFIX}: {self._room_name}",
            "manufacturer": "AV Scenes",
            "model": "Activity Controller",
            "suggested_area": self._room_name,
        }

    # ------------------------------------------------------------------

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
