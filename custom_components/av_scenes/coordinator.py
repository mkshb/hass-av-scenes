"""Coordinator for AV Scenes integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
)

from .const import (
    DOMAIN,
    CONF_ROOMS,
    CONF_ACTIVITIES,
    CONF_ENTITY_ID,
    CONF_INPUT_SOURCE,
    CONF_VOLUME_LEVEL,
    CONF_SOUND_MODE,
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_TRANSITION,
    CONF_POSITION,
    CONF_TILT_POSITION,
    CONF_ACTION,
    CONF_SERVICE_DATA,
    ACTIVITY_STATE_IDLE,
    ACTIVITY_STATE_STARTING,
    ACTIVITY_STATE_ACTIVE,
    ACTIVITY_STATE_STOPPING,
    CONF_STEPS,
    CONF_STEP_TYPE,
    CONF_STEP_DELAY_AFTER,
    CONF_STEP_PARAMETERS,
    STEP_TYPE_POWER_ON,
    STEP_TYPE_POWER_OFF,
    STEP_TYPE_SET_SOURCE,
    STEP_TYPE_SET_VOLUME,
    STEP_TYPE_SET_SOUND_MODE,
    STEP_TYPE_SET_BRIGHTNESS,
    STEP_TYPE_SET_COLOR_TEMP,
    STEP_TYPE_SET_POSITION,
    STEP_TYPE_SET_TILT,
    STEP_TYPE_CALL_ACTION,
    STEP_TYPE_DELAY,
)

_LOGGER = logging.getLogger(__name__)

# Type alias for step handler coroutines
_StepHandler = Callable[..., Coroutine[Any, Any, None]]


class AVScenesCoordinator(DataUpdateCoordinator):
    """Class to manage AV scenes and activities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # We update manually when activities change
            config_entry=entry,
        )
        self.entry = entry
        self.rooms: dict[str, dict[str, Any]] = {}
        self.active_activities: dict[str, str] = {}  # room_id -> activity_name
        self.activity_states: dict[str, str] = {}  # room_id -> state
        self._room_locks: dict[str, asyncio.Lock] = {}

        # Dispatch table: step_type -> handler method
        # Built after __init__ so self is available.
        self._step_dispatch: dict[str, _StepHandler] = {
            STEP_TYPE_POWER_ON: self._step_power_on,
            STEP_TYPE_POWER_OFF: self._turn_off_device,
            STEP_TYPE_SET_SOURCE: self._step_set_source,
            STEP_TYPE_SET_VOLUME: self._step_set_volume,
            STEP_TYPE_SET_SOUND_MODE: self._step_set_sound_mode,
            STEP_TYPE_SET_BRIGHTNESS: self._step_set_brightness,
            STEP_TYPE_SET_COLOR_TEMP: self._step_set_color_temp,
            STEP_TYPE_SET_POSITION: self._step_set_position,
            STEP_TYPE_SET_TILT: self._step_set_tilt,
            STEP_TYPE_CALL_ACTION: self._step_call_action,
            # STEP_TYPE_DELAY: no handler — the delay is applied via delay_after only
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from config."""
        self.rooms = self.entry.data.get(CONF_ROOMS, {})
        return {
            "rooms": self.rooms,
            "active_activities": self.active_activities,
            "activity_states": self.activity_states,
        }

    async def async_start_activity(self, room_id: str, activity_name: str) -> None:
        """Start an activity in a room."""
        lock = self._room_locks.setdefault(room_id, asyncio.Lock())
        async with lock:
            await self._async_start_activity_locked(room_id, activity_name)

    async def _async_start_activity_locked(
        self, room_id: str, activity_name: str
    ) -> None:
        """Start an activity in a room (must be called with room lock held)."""
        _LOGGER.info("Starting activity '%s' in room '%s'", activity_name, room_id)

        if room_id not in self.rooms:
            _LOGGER.error("Room '%s' not found", room_id)
            return

        room = self.rooms[room_id]
        activities = room.get(CONF_ACTIVITIES, {})

        if activity_name not in activities:
            _LOGGER.error("Activity '%s' not found in room '%s'", activity_name, room_id)
            return

        new_activity = activities[activity_name]
        new_steps = new_activity.get(CONF_STEPS, [])

        if not new_steps:
            _LOGGER.warning("Activity '%s' has no steps configured", activity_name)
            return

        # Smart switching: turn off devices that are no longer needed
        if room_id in self.active_activities:
            old_activity_name = self.active_activities[room_id]
            if old_activity_name != activity_name:
                _LOGGER.info(
                    "Switching from '%s' to '%s'", old_activity_name, activity_name
                )
                old_steps = activities.get(old_activity_name, {}).get(CONF_STEPS, [])
                old_entities = self._get_entities_from_steps(old_steps)
                new_entities = self._get_entities_from_steps(new_steps)
                entities_to_turn_off = old_entities - new_entities

                if entities_to_turn_off:
                    _LOGGER.info(
                        "Turning off devices no longer needed: %s", entities_to_turn_off
                    )
                    for entity_id in entities_to_turn_off:
                        try:
                            await self._turn_off_device(entity_id)
                        except Exception as ex:
                            _LOGGER.error("Error turning off %s: %s", entity_id, ex)

        self.activity_states[room_id] = ACTIVITY_STATE_STARTING
        self.async_update_listeners()

        for idx, step in enumerate(new_steps, 1):
            step_type = step.get(CONF_STEP_TYPE)
            entity_id = step.get(CONF_ENTITY_ID, "")
            delay_after = step.get(CONF_STEP_DELAY_AFTER, 0)
            parameters = step.get(CONF_STEP_PARAMETERS, {})

            _LOGGER.info(
                "Executing step %d/%d: %s on %s", idx, len(new_steps), step_type, entity_id
            )

            try:
                await self._execute_step(step_type, entity_id, parameters)
            except Exception as ex:
                _LOGGER.error("Error executing step %d (%s): %s", idx, step_type, ex)
                # Continue with next step even if this one fails

            if delay_after > 0:
                _LOGGER.debug("Waiting %s seconds after step %d", delay_after, idx)
                await asyncio.sleep(delay_after)

        self.active_activities[room_id] = activity_name
        self.activity_states[room_id] = ACTIVITY_STATE_ACTIVE
        self.async_update_listeners()

        _LOGGER.info(
            "Activity '%s' started successfully in room '%s'", activity_name, room_id
        )

    def _get_entities_from_steps(self, steps: list[dict[str, Any]]) -> set[str]:
        """Extract unique entity IDs from a list of steps."""
        return {
            step[CONF_ENTITY_ID]
            for step in steps
            if step.get(CONF_ENTITY_ID, "").strip()
        }

    async def async_stop_activity(self, room_id: str) -> None:
        """Stop the current activity in a room."""
        lock = self._room_locks.setdefault(room_id, asyncio.Lock())
        async with lock:
            await self._async_stop_activity_locked(room_id)

    async def _async_stop_activity_locked(self, room_id: str) -> None:
        """Stop the current activity in a room (must be called with room lock held)."""
        if room_id not in self.active_activities:
            _LOGGER.debug("No active activity in room '%s'", room_id)
            return

        activity_name = self.active_activities[room_id]
        _LOGGER.info("Stopping activity '%s' in room '%s'", activity_name, room_id)

        self.activity_states[room_id] = ACTIVITY_STATE_STOPPING
        self.async_update_listeners()

        room = self.rooms[room_id]
        steps = room.get(CONF_ACTIVITIES, {}).get(activity_name, {}).get(CONF_STEPS, [])

        # Build an ordered, deduplicated (entity_id, delay_after) list.
        # Preserve first-occurrence order; track the highest delay_after seen per entity
        # so that the shutdown sequence respects the original timing requirements
        # (e.g. a TV that needs 5 s to power up also needs time to shut down cleanly).
        entity_delays: dict[str, int] = {}   # entity_id -> max delay_after across all steps
        entity_order: list[str] = []
        for step in steps:
            entity_id = step.get(CONF_ENTITY_ID, "").strip()
            if not entity_id:
                continue
            delay = step.get(CONF_STEP_DELAY_AFTER, 0)
            if entity_id not in entity_delays:
                entity_order.append(entity_id)
                entity_delays[entity_id] = delay
            else:
                entity_delays[entity_id] = max(entity_delays[entity_id], delay)

        shutdown_sequence = [(eid, entity_delays[eid]) for eid in entity_order]
        for entity_id, delay_after in reversed(shutdown_sequence):
            try:
                await self._turn_off_device(entity_id)
            except Exception as ex:
                _LOGGER.error("Error turning off %s: %s", entity_id, ex)
            if delay_after > 0:
                _LOGGER.debug(
                    "Waiting %s s after turning off %s", delay_after, entity_id
                )
                await asyncio.sleep(delay_after)

        del self.active_activities[room_id]
        self.activity_states[room_id] = ACTIVITY_STATE_IDLE
        self.async_update_listeners()

        _LOGGER.info("Activity '%s' stopped in room '%s'", activity_name, room_id)

    async def _turn_off_device(self, entity_id: str) -> None:
        """Turn off a device."""
        domain = entity_id.split(".")[0]
        if domain == "cover":
            await self.hass.services.async_call(
                domain,
                "close_cover",
                {ATTR_ENTITY_ID: entity_id},
                blocking=False,
            )
        else:
            await self.hass.services.async_call(
                "homeassistant",
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: entity_id},
                blocking=False,
            )

    async def _execute_step(
        self, step_type: str, entity_id: str, parameters: dict[str, Any]
    ) -> None:
        """Execute a single step using the dispatch table."""
        if step_type == STEP_TYPE_DELAY:
            # Pure delay step: no device action — delay_after provides the wait
            return

        handler = self._step_dispatch.get(step_type)
        if handler is None:
            _LOGGER.warning("Unknown step type: %s", step_type)
            return

        try:
            # power_on / power_off only need entity_id; all others need parameters too
            if step_type in (STEP_TYPE_POWER_ON, STEP_TYPE_POWER_OFF):
                await handler(entity_id)
            elif step_type == STEP_TYPE_CALL_ACTION:
                await handler(parameters)
            else:
                await handler(entity_id, parameters)
        except Exception as ex:
            _LOGGER.error("Error executing step %s on %s: %s", step_type, entity_id, ex)
            raise

    async def _step_power_on(self, entity_id: str) -> None:
        """Turn on a device."""
        domain = entity_id.split(".")[0]
        if domain == "cover":
            await self.hass.services.async_call(
                domain, "open_cover", {ATTR_ENTITY_ID: entity_id}, blocking=False
            )
        else:
            await self.hass.services.async_call(
                "homeassistant", SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=False
            )

    async def _step_set_source(self, entity_id: str, parameters: dict[str, Any]) -> None:
        """Set input source on media player."""
        source = parameters.get(CONF_INPUT_SOURCE)
        if source:
            await self.hass.services.async_call(
                "media_player",
                "select_source",
                {ATTR_ENTITY_ID: entity_id, "source": source},
                blocking=False,
            )
            _LOGGER.info("Set source to '%s' on %s", source, entity_id)

    async def _step_set_volume(self, entity_id: str, parameters: dict[str, Any]) -> None:
        """Set volume on media player."""
        volume_level = parameters.get(CONF_VOLUME_LEVEL)
        if volume_level is not None:
            await self.hass.services.async_call(
                "media_player",
                "volume_set",
                {ATTR_ENTITY_ID: entity_id, "volume_level": volume_level},
                blocking=False,
            )
            _LOGGER.info("Set volume to %d%% on %s", int(volume_level * 100), entity_id)

    async def _step_set_sound_mode(
        self, entity_id: str, parameters: dict[str, Any]
    ) -> None:
        """Set sound mode on media player."""
        sound_mode = parameters.get(CONF_SOUND_MODE)
        if sound_mode:
            await self.hass.services.async_call(
                "media_player",
                "select_sound_mode",
                {ATTR_ENTITY_ID: entity_id, "sound_mode": sound_mode},
                blocking=False,
            )
            _LOGGER.info("Set sound mode to '%s' on %s", sound_mode, entity_id)

    async def _step_set_brightness(
        self, entity_id: str, parameters: dict[str, Any]
    ) -> None:
        """Set brightness and optional color/transition on light."""
        service_data: dict[str, Any] = {ATTR_ENTITY_ID: entity_id}

        for param, key in (
            (CONF_BRIGHTNESS, "brightness"),
            (CONF_COLOR_TEMP, "color_temp"),
            (CONF_TRANSITION, "transition"),
        ):
            value = parameters.get(param)
            if value is not None:
                service_data[key] = value

        if len(service_data) > 1:
            await self.hass.services.async_call(
                "light", SERVICE_TURN_ON, service_data, blocking=False
            )
            _LOGGER.info("Set light settings on %s", entity_id)

    async def _step_set_color_temp(
        self, entity_id: str, parameters: dict[str, Any]
    ) -> None:
        """Set color temperature on light."""
        color_temp = parameters.get(CONF_COLOR_TEMP)
        if color_temp is not None:
            await self.hass.services.async_call(
                "light",
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_id, "color_temp": color_temp},
                blocking=False,
            )
            _LOGGER.info("Set color temp to %s on %s", color_temp, entity_id)

    async def _step_set_position(
        self, entity_id: str, parameters: dict[str, Any]
    ) -> None:
        """Set position on cover."""
        position = parameters.get(CONF_POSITION)
        if position is not None:
            await self.hass.services.async_call(
                "cover",
                "set_cover_position",
                {ATTR_ENTITY_ID: entity_id, "position": position},
                blocking=False,
            )
            _LOGGER.info("Set cover position to %d%% on %s", position, entity_id)

    async def _step_set_tilt(self, entity_id: str, parameters: dict[str, Any]) -> None:
        """Set tilt on cover."""
        tilt = parameters.get(CONF_TILT_POSITION)
        if tilt is not None:
            await self.hass.services.async_call(
                "cover",
                "set_cover_tilt_position",
                {ATTR_ENTITY_ID: entity_id, "tilt_position": tilt},
                blocking=False,
            )
            _LOGGER.info("Set cover tilt to %d%% on %s", tilt, entity_id)

    async def _step_call_action(self, parameters: dict[str, Any]) -> None:
        """Call a Home Assistant action/service."""
        action = parameters.get(CONF_ACTION)
        if not action:
            _LOGGER.error("No action specified for call_action step")
            return

        try:
            domain, service = action.split(".", 1)
        except ValueError:
            _LOGGER.error(
                "Invalid action format: '%s'. Expected format: domain.service", action
            )
            return

        service_data = parameters.get(CONF_SERVICE_DATA, {})
        _LOGGER.info("Calling action '%s' with data: %s", action, service_data)
        await self.hass.services.async_call(domain, service, service_data, blocking=False)
        _LOGGER.info("Dispatched action '%s'", action)
