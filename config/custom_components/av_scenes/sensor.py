"""Sensor platform for AV Scenes integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_ACTIVITIES,
    CONF_DEVICES,
    CONF_INPUT_SOURCE,
    CONF_POWER_ON_DELAY,
    CONF_IS_VOLUME_CONTROLLER,
    CONF_VOLUME_LEVEL,
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_TRANSITION,
    CONF_POSITION,
    CONF_TILT_POSITION,
    CONF_DEVICE_ORDER,
)
from .coordinator import AVScenesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AV Scenes sensors from a config entry."""
    coordinator: AVScenesCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []

    # Create a sensor for each room to show configuration details
    for room_id in coordinator.rooms.keys():
        sensors.append(RoomConfigSensor(coordinator, room_id))

    async_add_entities(sensors)
    _LOGGER.info(f"Created {len(sensors)} room configuration sensors")


class RoomConfigSensor(CoordinatorEntity, SensorEntity):
    """Representation of a room configuration sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "room_config"

    def __init__(
        self,
        coordinator: AVScenesCoordinator,
        room_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.room_id = room_id

        room_name = coordinator.rooms[room_id].get("name", room_id)
        self._attr_name = f"{room_name} Configuration"
        self._attr_unique_id = f"{DOMAIN}_config_{room_id}"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        # Show current activity or "idle"
        if self.room_id in self.coordinator.active_activities:
            return self.coordinator.active_activities[self.room_id]
        return "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed configuration as attributes."""
        room_data = self.coordinator.rooms.get(self.room_id, {})
        activities = room_data.get(CONF_ACTIVITIES, {})

        attrs = {
            "room_id": self.room_id,
            "room_name": room_data.get("name", self.room_id),
            "total_activities": len(activities),
            "activity_names": list(activities.keys()),
        }

        # Add detailed information for each activity
        activities_detail = {}
        for activity_name, activity_data in activities.items():
            devices = activity_data.get(CONF_DEVICES, {})
            device_order = activity_data.get(CONF_DEVICE_ORDER, list(devices.keys()))

            # Build device details in the correct order
            devices_detail = []
            for idx, device_id in enumerate(device_order, 1):
                if device_id not in devices:
                    continue

                device_config = devices[device_id]
                device_detail = {
                    "order": idx,
                    "entity_id": device_id,
                    "friendly_name": self._get_friendly_name(device_id),
                }

                # Add relevant configuration based on what's set
                if CONF_INPUT_SOURCE in device_config:
                    device_detail["input_source"] = device_config[CONF_INPUT_SOURCE]
                if CONF_POWER_ON_DELAY in device_config:
                    device_detail["delay"] = f"{device_config[CONF_POWER_ON_DELAY]}s"
                if CONF_IS_VOLUME_CONTROLLER in device_config:
                    device_detail["volume_controller"] = device_config[CONF_IS_VOLUME_CONTROLLER]
                if CONF_VOLUME_LEVEL in device_config:
                    device_detail["volume"] = f"{device_config[CONF_VOLUME_LEVEL]}%"
                if CONF_BRIGHTNESS in device_config:
                    device_detail["brightness"] = f"{device_config[CONF_BRIGHTNESS]}%"
                if CONF_COLOR_TEMP in device_config:
                    device_detail["color_temp"] = f"{device_config[CONF_COLOR_TEMP]} mired"
                if CONF_TRANSITION in device_config:
                    device_detail["transition"] = f"{device_config[CONF_TRANSITION]}s"
                if CONF_POSITION in device_config:
                    device_detail["position"] = f"{device_config[CONF_POSITION]}%"
                if CONF_TILT_POSITION in device_config:
                    device_detail["tilt_position"] = f"{device_config[CONF_TILT_POSITION]}%"

                devices_detail.append(device_detail)

            activities_detail[activity_name] = {
                "device_count": len(devices),
                "devices": devices_detail,
            }

        attrs["activities"] = activities_detail

        # Add current activity info if active
        if self.room_id in self.coordinator.active_activities:
            attrs["current_activity"] = self.coordinator.active_activities[self.room_id]
            attrs["status"] = "active"
        else:
            attrs["status"] = "idle"

        return attrs

    def _get_friendly_name(self, entity_id: str) -> str:
        """Get friendly name for an entity."""
        if not self.hass:
            return entity_id

        state = self.hass.states.get(entity_id)
        if state and state.attributes.get("friendly_name"):
            return state.attributes["friendly_name"]
        return entity_id

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

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self.room_id in self.coordinator.active_activities:
            return "mdi:play-circle"
        return "mdi:information-outline"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
