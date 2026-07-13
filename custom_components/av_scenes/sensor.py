"""Sensor platform for AV Scenes integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_ACTIVITIES,
    CONF_STEPS,
    CONF_STEP_TYPE,
    CONF_ENTITY_ID,
    CONF_STEP_DELAY_AFTER,
    ACTIVITY_STATE_IDLE,
    ACTIVITY_STATE_STARTING,
    ACTIVITY_STATE_ACTIVE,
    ACTIVITY_STATE_STOPPING,
    ACTIVITY_STATE_ERROR,
)
from .coordinator import AVScenesConfigEntry, AVScenesCoordinator
from .entity import AVRoomEntity

_LOGGER = logging.getLogger(__name__)

# Icon per activity state
_STATE_ICONS: dict[str, str] = {
    ACTIVITY_STATE_IDLE:     "mdi:television-off",
    ACTIVITY_STATE_STARTING: "mdi:timer-sand",
    ACTIVITY_STATE_ACTIVE:   "mdi:play-circle",
    ACTIVITY_STATE_STOPPING: "mdi:stop-circle-outline",
    ACTIVITY_STATE_ERROR:    "mdi:alert-circle",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AVScenesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AV Scenes sensors from a config entry."""
    coordinator = entry.runtime_data

    sensors = [
        RoomActivitySensor(coordinator, room_id)
        for room_id in coordinator.rooms
    ]
    async_add_entities(sensors)
    _LOGGER.debug("Created %d room activity sensors", len(sensors))


class RoomActivitySensor(AVRoomEntity, SensorEntity):
    """Sensor that exposes the current activity state of a room.

    State values: idle | starting | active | stopping | error
    Attributes:   activity_name, current_step, total_steps, step_progress_pct,
                  available_activities
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        ACTIVITY_STATE_IDLE,
        ACTIVITY_STATE_STARTING,
        ACTIVITY_STATE_ACTIVE,
        ACTIVITY_STATE_STOPPING,
        ACTIVITY_STATE_ERROR,
    ]

    _attr_translation_key = "activity_state"

    def __init__(self, coordinator: AVScenesCoordinator, room_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, room_id)
        self._attr_unique_id = f"{DOMAIN}_activity_state_{room_id}"

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def native_value(self) -> str:
        """Return the current activity state (idle/starting/active/stopping)."""
        return self.coordinator.activity_states.get(self.room_id, ACTIVITY_STATE_IDLE)

    # ------------------------------------------------------------------
    # Attributes
    # ------------------------------------------------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return progress and configuration details."""
        room_data = self.coordinator.rooms.get(self.room_id, {})
        activities: dict[str, Any] = room_data.get(CONF_ACTIVITIES, {})

        # Current activity name (None when idle)
        activity_name: str | None = self.coordinator.active_activities.get(self.room_id)

        # Step progress
        current_step, total_steps = self.coordinator.activity_progress.get(
            self.room_id, (0, 0)
        )
        step_progress_pct = (
            round(current_step / total_steps * 100) if total_steps else 0
        )

        attrs: dict[str, Any] = {
            "activity_name": activity_name,
            "available_activities": list(activities.keys()),
            "current_step": current_step,
            "total_steps": total_steps,
            "step_progress_pct": step_progress_pct,
        }

        # Step summary for the active activity (label list, useful in Markdown card)
        if activity_name and activity_name in activities:
            steps = activities[activity_name].get(CONF_STEPS, [])
            attrs["steps"] = [
                {
                    "nr": i + 1,
                    "type": s.get(CONF_STEP_TYPE, ""),
                    "entity": s.get(CONF_ENTITY_ID, ""),
                    "delay_after": s.get(CONF_STEP_DELAY_AFTER, 0),
                }
                for i, s in enumerate(steps)
            ]

        return attrs

    # ------------------------------------------------------------------
    # Icon — changes with state
    # ------------------------------------------------------------------

    @property
    def icon(self) -> str:
        """Return state-dependent icon."""
        return _STATE_ICONS.get(self.native_value, "mdi:television")
