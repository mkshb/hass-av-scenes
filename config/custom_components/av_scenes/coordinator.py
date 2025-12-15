"""Coordinator for AV Scenes integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import entity_registry as er
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
    STATE_ON,
    STATE_OFF,
)

from .const import (
    DOMAIN,
    CONF_ROOMS,
    CONF_ACTIVITIES,
    CONF_DEVICES,
    CONF_DEVICE_STATES,
    CONF_POWER_ON_DELAY,
    CONF_POWER_OFF_DELAY,
    CONF_INPUT_SOURCE,
    CONF_VOLUME_LEVEL,
    CONF_IS_VOLUME_CONTROLLER,
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_RGB_COLOR,
    CONF_TRANSITION,
    CONF_POSITION,
    CONF_TILT_POSITION,
    DEFAULT_POWER_ON_DELAY,
    DEFAULT_POWER_OFF_DELAY,
    SERVICE_START_ACTIVITY,
    SERVICE_STOP_ACTIVITY,
    SERVICE_RELOAD,
    ATTR_ROOM,
    ATTR_ACTIVITY,
    ACTIVITY_STATE_IDLE,
    ACTIVITY_STATE_STARTING,
    ACTIVITY_STATE_ACTIVE,
    ACTIVITY_STATE_STOPPING,
)

_LOGGER = logging.getLogger(__name__)


class AVScenesCoordinator(DataUpdateCoordinator):
    """Class to manage AV scenes and activities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # We update manually when activities change
            config_entry=entry,  # Pass config entry to parent
        )
        self.entry = entry
        self.rooms: dict[str, dict[str, Any]] = {}
        self.active_activities: dict[str, str] = {}  # room_id -> activity_name
        self.activity_states: dict[str, str] = {}  # room_id -> state
        self._services_registered = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from config."""
        config_data = self.entry.data
        
        # Parse rooms and activities from config
        self.rooms = config_data.get(CONF_ROOMS, {})
        
        return {
            "rooms": self.rooms,
            "active_activities": self.active_activities,
            "activity_states": self.activity_states,
        }

    async def async_start_activity(
        self, room_id: str, activity_name: str
    ) -> None:
        """Start an activity in a room."""
        _LOGGER.info(f"Starting activity '{activity_name}' in room '{room_id}'")
        
        if room_id not in self.rooms:
            _LOGGER.error(f"Room '{room_id}' not found")
            return
        
        room = self.rooms[room_id]
        activities = room.get(CONF_ACTIVITIES, {})
        
        if activity_name not in activities:
            _LOGGER.error(f"Activity '{activity_name}' not found in room '{room_id}'")
            return
        
        # Get the new activity configuration
        new_activity = activities[activity_name]
        new_device_states = new_activity.get(CONF_DEVICE_STATES, {})
        
        # Check if there's a current activity running
        current_activity_name = self.active_activities.get(room_id)
        devices_to_keep_on = set()
        devices_to_turn_off = set()
        
        if current_activity_name:
            _LOGGER.info(f"Current activity '{current_activity_name}' is running, performing smart switch")
            
            # Get current activity configuration
            current_activity = activities.get(current_activity_name, {})
            current_device_states = current_activity.get(CONF_DEVICE_STATES, {})
            
            # Determine which devices are in both activities
            current_devices = set(current_device_states.keys())
            new_devices = set(new_device_states.keys())
            
            devices_to_keep_on = current_devices & new_devices  # Intersection
            devices_to_turn_off = current_devices - new_devices  # Only in current
            
            _LOGGER.info(
                f"Smart switch: keeping {len(devices_to_keep_on)} devices on, "
                f"turning off {len(devices_to_turn_off)} devices"
            )
            
            # Turn off devices that are not needed in new activity
            for device_id in devices_to_turn_off:
                await self._turn_off_device(device_id)
        
        # Set state to starting
        self.activity_states[room_id] = ACTIVITY_STATE_STARTING
        self.async_update_listeners()
        
        # Process all devices in new activity
        for device_id, state_config in new_device_states.items():
            if device_id in devices_to_keep_on:
                # Device is already on, just update settings (input source, volume)
                _LOGGER.info(f"Updating settings for already-on device: {device_id}")
                await self._update_device_settings(device_id, state_config)
            else:
                # Device needs to be turned on
                _LOGGER.info(f"Turning on device: {device_id}")
                await self._execute_device_command(device_id, state_config)
        
        # Mark activity as active
        self.active_activities[room_id] = activity_name
        self.activity_states[room_id] = ACTIVITY_STATE_ACTIVE
        self.async_update_listeners()
        
        _LOGGER.info(f"Activity '{activity_name}' started successfully in room '{room_id}'")

    async def async_stop_activity(self, room_id: str) -> None:
        """Stop the current activity in a room."""
        if room_id not in self.active_activities:
            _LOGGER.debug(f"No active activity in room '{room_id}'")
            return
        
        activity_name = self.active_activities[room_id]
        _LOGGER.info(f"Stopping activity '{activity_name}' in room '{room_id}'")
        
        # Set state to stopping
        self.activity_states[room_id] = ACTIVITY_STATE_STOPPING
        self.async_update_listeners()
        
        room = self.rooms[room_id]
        activities = room.get(CONF_ACTIVITIES, {})
        activity = activities.get(activity_name, {})
        device_states = activity.get(CONF_DEVICE_STATES, {})
        
        # Turn off devices
        for device_id in device_states.keys():
            await self._turn_off_device(device_id)
        
        # Clear active activity
        del self.active_activities[room_id]
        self.activity_states[room_id] = ACTIVITY_STATE_IDLE
        self.async_update_listeners()
        
        _LOGGER.info(f"Activity '{activity_name}' stopped in room '{room_id}'")

    async def _execute_device_command(
        self, entity_id: str, state_config: dict[str, Any]
    ) -> None:
        """Execute a command for a device."""
        try:
            domain = entity_id.split(".")[0]

            # Cover entities use different services
            if domain == "cover":
                # For covers, directly apply settings (open/position/tilt)
                # No generic turn_on, just set the desired state
                await self._update_device_settings(entity_id, state_config)

                # Wait for power-on delay (useful for sequential cover operations)
                delay = state_config.get(CONF_POWER_ON_DELAY, DEFAULT_POWER_ON_DELAY)
                if delay > 0:
                    await asyncio.sleep(delay)
            else:
                # For other entities (media_player, light, switch), turn on first
                await self.hass.services.async_call(
                    "homeassistant",
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: entity_id},
                    blocking=True,
                )

                # Wait for power-on delay
                delay = state_config.get(CONF_POWER_ON_DELAY, DEFAULT_POWER_ON_DELAY)
                if delay > 0:
                    await asyncio.sleep(delay)

                # Update settings (volume, input source, brightness, etc.)
                await self._update_device_settings(entity_id, state_config)

        except Exception as ex:
            _LOGGER.error(f"Error executing command for {entity_id}: {ex}")

    async def _update_device_settings(
        self, entity_id: str, state_config: dict[str, Any]
    ) -> None:
        """Update device settings without power cycling."""
        try:
            domain = entity_id.split(".")[0]

            # Media player specific settings
            if domain == "media_player":
                # Set volume if this is the volume controller
                if state_config.get(CONF_IS_VOLUME_CONTROLLER, False):
                    volume_level = state_config.get(CONF_VOLUME_LEVEL)
                    if volume_level is not None:
                        await self.hass.services.async_call(
                            domain,
                            "volume_set",
                            {
                                ATTR_ENTITY_ID: entity_id,
                                "volume_level": volume_level,
                            },
                            blocking=True,
                        )
                        _LOGGER.info(
                            "Set volume to %.0f%% on %s",
                            volume_level * 100,
                            entity_id
                        )

                # Set input source if specified
                input_source = state_config.get(CONF_INPUT_SOURCE)
                if input_source:
                    await self.hass.services.async_call(
                        domain,
                        "select_source",
                        {
                            ATTR_ENTITY_ID: entity_id,
                            "source": input_source,
                        },
                        blocking=True,
                    )
                    _LOGGER.info(
                        "Changed input source to '%s' on %s",
                        input_source,
                        entity_id
                    )

            # Light specific settings
            elif domain == "light":
                service_data = {ATTR_ENTITY_ID: entity_id}

                # Set brightness
                brightness = state_config.get(CONF_BRIGHTNESS)
                if brightness is not None:
                    service_data["brightness"] = brightness

                # Set color temperature
                color_temp = state_config.get(CONF_COLOR_TEMP)
                if color_temp is not None:
                    service_data["color_temp"] = color_temp

                # Set transition
                transition = state_config.get(CONF_TRANSITION)
                if transition is not None:
                    service_data["transition"] = transition

                # Only call turn_on if we have settings to apply
                if len(service_data) > 1:  # More than just entity_id
                    await self.hass.services.async_call(
                        domain,
                        SERVICE_TURN_ON,
                        service_data,
                        blocking=True,
                    )
                    _LOGGER.info("Updated light settings on %s", entity_id)

            # Cover specific settings
            elif domain == "cover":
                # Set position
                position = state_config.get(CONF_POSITION)
                if position is not None:
                    await self.hass.services.async_call(
                        domain,
                        "set_cover_position",
                        {
                            ATTR_ENTITY_ID: entity_id,
                            "position": position,
                        },
                        blocking=True,
                    )
                    _LOGGER.info("Set cover position to %d%% on %s", position, entity_id)
                else:
                    # If no position specified, just open the cover
                    await self.hass.services.async_call(
                        domain,
                        "open_cover",
                        {ATTR_ENTITY_ID: entity_id},
                        blocking=True,
                    )
                    _LOGGER.info("Opened cover %s", entity_id)

                # Set tilt position
                tilt_position = state_config.get(CONF_TILT_POSITION)
                if tilt_position is not None:
                    await self.hass.services.async_call(
                        domain,
                        "set_cover_tilt_position",
                        {
                            ATTR_ENTITY_ID: entity_id,
                            "tilt_position": tilt_position,
                        },
                        blocking=True,
                    )
                    _LOGGER.info("Set cover tilt to %d%% on %s", tilt_position, entity_id)

            # Switch has no additional settings to update

        except Exception as ex:
            _LOGGER.error(f"Error updating settings for {entity_id}: {ex}")

    async def _turn_off_device(self, entity_id: str) -> None:
        """Turn off a device."""
        try:
            domain = entity_id.split(".")[0]

            # Cover entities use close_cover instead of turn_off
            if domain == "cover":
                await self.hass.services.async_call(
                    domain,
                    "close_cover",
                    {ATTR_ENTITY_ID: entity_id},
                    blocking=True,
                )
            else:
                # For other entities, use generic turn_off
                await self.hass.services.async_call(
                    "homeassistant",
                    SERVICE_TURN_OFF,
                    {ATTR_ENTITY_ID: entity_id},
                    blocking=True,
                )
        except Exception as ex:
            _LOGGER.error(f"Error turning off {entity_id}: {ex}")

    async def async_register_services(self) -> None:
        """Register services."""
        if self._services_registered:
            return
        
        async def handle_start_activity(call: ServiceCall) -> None:
            """Handle start activity service call."""
            room_id = call.data.get(ATTR_ROOM)
            activity_name = call.data.get(ATTR_ACTIVITY)
            await self.async_start_activity(room_id, activity_name)
        
        async def handle_stop_activity(call: ServiceCall) -> None:
            """Handle stop activity service call."""
            room_id = call.data.get(ATTR_ROOM)
            await self.async_stop_activity(room_id)
        
        async def handle_reload(call: ServiceCall) -> None:
            """Handle reload service call."""
            await self.async_config_entry_first_refresh()
        
        self.hass.services.async_register(
            DOMAIN, SERVICE_START_ACTIVITY, handle_start_activity
        )
        self.hass.services.async_register(
            DOMAIN, SERVICE_STOP_ACTIVITY, handle_stop_activity
        )
        self.hass.services.async_register(
            DOMAIN, SERVICE_RELOAD, handle_reload
        )
        
        self._services_registered = True
        _LOGGER.debug("Services registered")

    async def async_unregister_services(self) -> None:
        """Unregister services."""
        if not self._services_registered:
            return
        
        self.hass.services.async_remove(DOMAIN, SERVICE_START_ACTIVITY)
        self.hass.services.async_remove(DOMAIN, SERVICE_STOP_ACTIVITY)
        self.hass.services.async_remove(DOMAIN, SERVICE_RELOAD)
        
        self._services_registered = False
        _LOGGER.debug("Services unregistered")
