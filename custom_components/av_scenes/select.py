"""Select platform for AV Scenes integration.

Provides one SelectEntity per room that:
 - shows the active activity name (or a status label during transitions)
 - lets the user start an activity by selecting its name
 - lets the user stop the current activity by selecting "idle" (shown as "—")
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
    ACTIVITY_STATE_ERROR,
)
from .coordinator import AVScenesCoordinator

_LOGGER = logging.getLogger(__name__)

# Fixed options for idle and the transitional states; their labels come from
# the state translations (entity.select.scene.state). Activities are listed by
# their display name, which is not translated.
_OPT_IDLE = ACTIVITY_STATE_IDLE
_OPT_STARTING = ACTIVITY_STATE_STARTING
_OPT_STOPPING = ACTIVITY_STATE_STOPPING
_OPT_ERROR = ACTIVITY_STATE_ERROR

# Options the user must not be able to actively choose
_READONLY_OPTIONS = {_OPT_STARTING, _OPT_STOPPING, _OPT_ERROR}


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
    _attr_translation_key = "scene"
    _attr_icon = "mdi:play-circle-outline"

    def __init__(self, coordinator: AVScenesCoordinator, room_id: str) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.room_id = room_id

        room_data = coordinator.rooms[room_id]
        self._room_name: str = room_data.get("name", room_id)
        self._attr_unique_id = f"{DOMAIN}_select_{room_id}"

    # ------------------------------------------------------------------
    # Options — activity names + idle; transitional states added live
    # ------------------------------------------------------------------

    @property
    def options(self) -> list[str]:
        """Return all selectable options plus any active status label."""
        activities = [
            self.coordinator.activity_name(self.room_id, activity_id)
            for activity_id in self.coordinator.rooms.get(self.room_id, {}).get(
                CONF_ACTIVITIES, {}
            )
        ]
        base = [_OPT_IDLE] + activities

        state = self.coordinator.activity_states.get(self.room_id, ACTIVITY_STATE_IDLE)
        if state == ACTIVITY_STATE_STARTING:
            return [_OPT_STARTING] + base
        if state == ACTIVITY_STATE_STOPPING:
            return [_OPT_STOPPING] + base
        if state == ACTIVITY_STATE_ERROR:
            return [_OPT_ERROR] + base
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
        if state == ACTIVITY_STATE_ERROR:
            return _OPT_ERROR

        activity = self.coordinator.active_activities.get(self.room_id)
        if not activity:
            return _OPT_IDLE
        return self.coordinator.activity_name(self.room_id, activity)

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
