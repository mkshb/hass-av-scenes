"""Config flow for AV Scenes integration."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import area_registry as ar, selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_ROOMS,
    CONF_ACTIVITIES,
    CONF_DEVICES,
    CONF_DEVICE_STATES,
    CONF_DEVICE_ORDER,
    CONF_ACTIVITY_NAME,
    CONF_ENTITY_ID,
    CONF_INPUT_SOURCE,
    CONF_POWER_ON_DELAY,
    CONF_VOLUME_LEVEL,
    CONF_SOUND_MODE,
    CONF_IS_VOLUME_CONTROLLER,
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_TRANSITION,
    CONF_POSITION,
    CONF_TILT_POSITION,
    CONF_ACTION,
    CONF_SERVICE_DATA,
    DEFAULT_POWER_ON_DELAY,
    # Step-based configuration
    CONF_STEPS,
    CONF_STEP_ID,
    CONF_STEP_TYPE,
    CONF_STEP_DELAY_AFTER,
    CONF_STEP_PARAMETERS,
    STEP_TYPE_POWER_ON,
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
from .config_flow_rooms import RoomsFlowMixin
from .config_flow_activities import ActivitiesFlowMixin
from .config_flow_devices import DevicesFlowMixin
from .config_flow_steps import StepsFlowMixin

_LOGGER = logging.getLogger(__name__)


def _migrate_device_states_to_steps(activity_data: dict[str, Any]) -> dict[str, Any]:
    """Migrate old device_states format to new steps format."""
    # If already using steps, return as-is
    if CONF_STEPS in activity_data:
        return activity_data

    # If no device_states, create empty steps
    if CONF_DEVICE_STATES not in activity_data:
        return {CONF_STEPS: []}

    device_states = activity_data.get(CONF_DEVICE_STATES, {})
    device_order = activity_data.get(CONF_DEVICE_ORDER, list(device_states.keys()))

    steps = []

    for entity_id in device_order:
        config = device_states.get(entity_id)
        if not config:
            continue

        domain = entity_id.split(".")[0]
        delay_after = config.get(CONF_POWER_ON_DELAY, DEFAULT_POWER_ON_DELAY)

        # Create power_on step
        power_on_step = {
            CONF_STEP_ID: str(uuid.uuid4()),
            CONF_STEP_TYPE: STEP_TYPE_POWER_ON,
            CONF_ENTITY_ID: entity_id,
            CONF_STEP_DELAY_AFTER: 0,  # No delay after power on
            CONF_STEP_PARAMETERS: {},
        }
        steps.append(power_on_step)

        # Add domain-specific configuration steps
        if domain == "media_player":
            # Input source step
            input_source = config.get(CONF_INPUT_SOURCE)
            if input_source:
                source_step = {
                    CONF_STEP_ID: str(uuid.uuid4()),
                    CONF_STEP_TYPE: STEP_TYPE_SET_SOURCE,
                    CONF_ENTITY_ID: entity_id,
                    CONF_STEP_DELAY_AFTER: 0,
                    CONF_STEP_PARAMETERS: {
                        CONF_INPUT_SOURCE: input_source,
                    },
                }
                steps.append(source_step)

            # Volume step
            if config.get(CONF_IS_VOLUME_CONTROLLER, False):
                volume_level = config.get(CONF_VOLUME_LEVEL, 0.5)
                volume_step = {
                    CONF_STEP_ID: str(uuid.uuid4()),
                    CONF_STEP_TYPE: STEP_TYPE_SET_VOLUME,
                    CONF_ENTITY_ID: entity_id,
                    CONF_STEP_DELAY_AFTER: delay_after,  # Apply delay after volume
                    CONF_STEP_PARAMETERS: {
                        CONF_VOLUME_LEVEL: volume_level,
                    },
                }
                steps.append(volume_step)
            else:
                # Apply delay after power_on if no other steps
                power_on_step[CONF_STEP_DELAY_AFTER] = delay_after

        elif domain == "light":
            # Brightness step
            brightness = config.get(CONF_BRIGHTNESS)
            color_temp = config.get(CONF_COLOR_TEMP)
            transition = config.get(CONF_TRANSITION)

            if brightness is not None or color_temp is not None:
                light_step = {
                    CONF_STEP_ID: str(uuid.uuid4()),
                    CONF_STEP_TYPE: STEP_TYPE_SET_BRIGHTNESS,
                    CONF_ENTITY_ID: entity_id,
                    CONF_STEP_DELAY_AFTER: delay_after,
                    CONF_STEP_PARAMETERS: {},
                }

                if brightness is not None:
                    light_step[CONF_STEP_PARAMETERS][CONF_BRIGHTNESS] = brightness
                if color_temp is not None:
                    light_step[CONF_STEP_PARAMETERS][CONF_COLOR_TEMP] = color_temp
                if transition is not None:
                    light_step[CONF_STEP_PARAMETERS][CONF_TRANSITION] = transition

                steps.append(light_step)
            else:
                power_on_step[CONF_STEP_DELAY_AFTER] = delay_after

        elif domain == "cover":
            # Position step
            position = config.get(CONF_POSITION)
            tilt_position = config.get(CONF_TILT_POSITION)

            if position is not None:
                position_step = {
                    CONF_STEP_ID: str(uuid.uuid4()),
                    CONF_STEP_TYPE: STEP_TYPE_SET_POSITION,
                    CONF_ENTITY_ID: entity_id,
                    CONF_STEP_DELAY_AFTER: 0,
                    CONF_STEP_PARAMETERS: {
                        CONF_POSITION: position,
                    },
                }
                steps.append(position_step)

            if tilt_position is not None:
                tilt_step = {
                    CONF_STEP_ID: str(uuid.uuid4()),
                    CONF_STEP_TYPE: STEP_TYPE_SET_TILT,
                    CONF_ENTITY_ID: entity_id,
                    CONF_STEP_DELAY_AFTER: delay_after,
                    CONF_STEP_PARAMETERS: {
                        CONF_TILT_POSITION: tilt_position,
                    },
                }
                steps.append(tilt_step)
            elif not steps or steps[-1][CONF_STEP_DELAY_AFTER] == 0:
                # Apply delay to last step
                if steps:
                    steps[-1][CONF_STEP_DELAY_AFTER] = delay_after

        else:
            # For switch or other domains, just apply delay
            power_on_step[CONF_STEP_DELAY_AFTER] = delay_after

    return {CONF_STEPS: steps}


class AVScenesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AV Scenes."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.rooms: dict[str, Any] = {}
        self.current_room: str | None = None
        self.current_room_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Create entry with initial empty configuration
            return self.async_create_entry(
                title="AV Scenes",
                data={CONF_ROOMS: {}},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={
                "info": "This integration allows you to create activity-based scenes for your AV equipment. "
                "After setup, use the options flow to configure rooms and activities."
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AVScenesOptionsFlow:
        """Get the options flow for this handler."""
        return AVScenesOptionsFlow(config_entry)


class AVScenesOptionsFlow(
    RoomsFlowMixin,
    ActivitiesFlowMixin,
    DevicesFlowMixin,
    StepsFlowMixin,
    config_entries.OptionsFlow,
):
    """Handle options flow for AV Scenes."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        _LOGGER.debug("Initializing OptionsFlow for entry: %s", config_entry.entry_id)

        try:
            import copy
            # Make a deep copy to avoid modifying the original
            rooms_data = config_entry.data.get(CONF_ROOMS, {})
            if not isinstance(rooms_data, dict):
                _LOGGER.warning("Rooms data is not a dict, using empty dict")
                rooms_data = {}

            self.rooms: dict[str, Any] = copy.deepcopy(rooms_data)

            # Log loaded step order so any later reordering is traceable
            for room_id, room_data in self.rooms.items():
                for act_name, act_data in room_data.get(CONF_ACTIVITIES, {}).items():
                    steps = act_data.get(CONF_STEPS, [])
                    step_summary = [
                        f"{i+1}:{s.get(CONF_STEP_TYPE,'?')}@{s.get(CONF_ENTITY_ID,'')}"
                        for i, s in enumerate(steps)
                    ]
                    _LOGGER.debug(
                        "Loaded activity '%s' (%s) — %d steps: %s",
                        act_name, room_id, len(steps), step_summary,
                    )

            # Migrate old device_states format to new steps format
            migrated = False
            for room_id, room_data in self.rooms.items():
                activities = room_data.get(CONF_ACTIVITIES, {})
                for activity_name, activity_data in activities.items():
                    if CONF_DEVICE_STATES in activity_data and CONF_STEPS not in activity_data:
                        _LOGGER.info(
                            "Migrating activity '%s' in room '%s' from device_states to steps",
                            activity_name,
                            room_id
                        )
                        migrated_data = _migrate_device_states_to_steps(activity_data)
                        activities[activity_name] = migrated_data
                        migrated = True

            if migrated:
                _LOGGER.info("Migration completed, saving config")
                self.config_entry = config_entry
                # Mark that we need to save on first opportunity
                self._needs_migration_save = True
            else:
                self._needs_migration_save = False

            self.current_room: str | None = None
            self.current_activity: str | None = None
            self.current_room_data: dict[str, Any] = {}
            self.current_activity_data: dict[str, Any] = {}
            self.current_step_data: dict[str, Any] = {}
            self.selected_step_id: str | None = None
            self._last_save_data: str | None = None  # Track last saved data to avoid duplicate saves

            _LOGGER.debug("OptionsFlow initialized with %d rooms", len(self.rooms))
        except Exception as ex:
            _LOGGER.exception("Error initializing OptionsFlow: %s", ex)
            # Initialize with empty data to prevent crashes
            self.rooms = {}
            self.current_room = None
            self.current_activity = None
            self.current_room_data = {}
            self.current_activity_data = {}
            self.current_step_data = {}
            self.selected_step_id = None
            self._last_save_data = None
            self._needs_migration_save = False

    def _save_config(self) -> None:
        """Save the current configuration to the config entry."""
        import json

        # Convert to JSON to check if data actually changed.
        # NOTE: sort_keys=True is intentional here — it is used ONLY for
        # change-detection.  The actual data written to the entry is
        # self.rooms (list order preserved).
        current_data = json.dumps(self.rooms, sort_keys=True)

        if current_data == self._last_save_data:
            _LOGGER.debug("Config unchanged, skipping save")
            return

        # Log step order for every activity so ordering issues are traceable
        for room_id, room_data in self.rooms.items():
            for activity_name, activity_data in room_data.get(CONF_ACTIVITIES, {}).items():
                steps = activity_data.get(CONF_STEPS, [])
                step_summary = [
                    f"{i+1}:{s.get(CONF_STEP_TYPE,'?')}@{s.get(CONF_ENTITY_ID,'')}"
                    for i, s in enumerate(steps)
                ]
                _LOGGER.debug(
                    "Saving activity '%s' (%s) — %d steps: %s",
                    activity_name, room_id, len(steps), step_summary,
                )

        _LOGGER.info("Saving configuration with %d rooms", len(self.rooms))
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={CONF_ROOMS: self.rooms}
        )
        self._last_save_data = current_data

    def _ensure_device_order(self, activity_data: dict[str, Any]) -> list[str]:
        """Ensure device_order exists and is synchronized with device_states."""
        device_states = activity_data.get(CONF_DEVICE_STATES, {})
        device_order = activity_data.get(CONF_DEVICE_ORDER, [])

        # If device_order doesn't exist or is out of sync, rebuild it from device_states
        device_state_keys = list(device_states.keys())

        # Remove any devices from order that no longer exist in device_states
        device_order = [d for d in device_order if d in device_states]

        # Add any new devices from device_states that aren't in order
        for device_id in device_state_keys:
            if device_id not in device_order:
                device_order.append(device_id)

        # Save the synchronized order back to activity_data
        activity_data[CONF_DEVICE_ORDER] = device_order

        return device_order

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        _LOGGER.debug("Options flow: async_step_init called")

        # Persist migration result immediately so the coordinator reloads
        # with the correct step order — and so the migration never re-runs.
        if self._needs_migration_save:
            _LOGGER.info("Persisting migrated activity data")
            self._save_config()
            self._needs_migration_save = False

        return await self.async_step_room_menu()
