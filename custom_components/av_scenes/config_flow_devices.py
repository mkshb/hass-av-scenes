"""Legacy device management mixin for AV Scenes config flow."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ACTIVITIES,
    CONF_DEVICE_STATES,
    CONF_DEVICE_ORDER,
    CONF_ENTITY_ID,
    CONF_INPUT_SOURCE,
    CONF_POWER_ON_DELAY,
    CONF_VOLUME_LEVEL,
    CONF_IS_VOLUME_CONTROLLER,
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_TRANSITION,
    CONF_POSITION,
    CONF_TILT_POSITION,
    DEFAULT_POWER_ON_DELAY,
)

_LOGGER = logging.getLogger(__name__)


class DevicesFlowMixin:
    """Mixin for legacy device management flow steps."""

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a device to the activity - step 1: select entity."""
        errors = {}

        if user_input is not None:
            try:
                entity_id = user_input.get(CONF_ENTITY_ID)

                # Validate entity exists
                state = self.hass.states.get(entity_id)
                if state is None:
                    errors[CONF_ENTITY_ID] = "entity_not_found"
                else:
                    # Store selected entity and move to details step
                    self.selected_device_id = entity_id
                    return await self.async_step_add_device_details()
            except Exception as ex:
                _LOGGER.exception("Error in add_device: %s", ex)
                errors["base"] = "unknown"

        # Get all supported entities (media_player, light, switch, cover)
        supported_domains = ["media_player", "light", "switch", "cover"]
        entities = []

        for domain in supported_domains:
            for entity_id in self.hass.states.async_entity_ids(domain):
                state = self.hass.states.get(entity_id)
                if state:
                    # Use friendly name if available
                    friendly_name = state.attributes.get("friendly_name", entity_id)
                    # Add domain prefix to make it clearer in the UI
                    display_name = f"[{domain}] {friendly_name}"
                    entities.append((entity_id, display_name))

        # Sort by display name
        entities.sort(key=lambda x: x[1])

        # Create entity selector options
        entity_options = {entity_id: name for entity_id, name in entities}

        if not entity_options:
            entity_options = {"": "No entities found"}

        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema({
                vol.Required(CONF_ENTITY_ID): vol.In(entity_options),
            }),
            errors=errors,
            description_placeholders={
                "room": self.current_room or "unknown",
                "activity": self.current_activity or "unknown",
            },
        )

    async def async_step_add_device_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a device to the activity - step 2: configure details."""
        errors = {}

        # Get entity domain
        domain = self.selected_device_id.split(".")[0]

        if user_input is not None:
            try:
                device_config = {
                    CONF_POWER_ON_DELAY: user_input.get(
                        CONF_POWER_ON_DELAY, DEFAULT_POWER_ON_DELAY
                    ),
                }

                # Media player specific configuration
                if domain == "media_player":
                    input_source = user_input.get(CONF_INPUT_SOURCE)
                    if input_source and input_source.strip() and input_source != "none":
                        device_config[CONF_INPUT_SOURCE] = input_source.strip()

                    # Volume control settings
                    is_volume_controller = user_input.get(CONF_IS_VOLUME_CONTROLLER, False)
                    if is_volume_controller:
                        device_config[CONF_IS_VOLUME_CONTROLLER] = True
                        volume_level = user_input.get(CONF_VOLUME_LEVEL)
                        if volume_level is not None:
                            # Convert percentage to 0.0-1.0 range
                            device_config[CONF_VOLUME_LEVEL] = volume_level / 100.0

                # Light specific configuration
                elif domain == "light":
                    brightness = user_input.get(CONF_BRIGHTNESS)
                    if brightness is not None:
                        # Convert percentage to 0-255 range
                        device_config[CONF_BRIGHTNESS] = int(brightness * 255 / 100)

                    color_temp = user_input.get(CONF_COLOR_TEMP)
                    if color_temp is not None:
                        device_config[CONF_COLOR_TEMP] = color_temp

                    transition = user_input.get(CONF_TRANSITION)
                    if transition is not None:
                        device_config[CONF_TRANSITION] = transition

                # Cover specific configuration
                elif domain == "cover":
                    position = user_input.get(CONF_POSITION)
                    if position is not None:
                        device_config[CONF_POSITION] = position

                    tilt_position = user_input.get(CONF_TILT_POSITION)
                    if tilt_position is not None:
                        device_config[CONF_TILT_POSITION] = tilt_position

                # Switch has no additional configuration beyond power_on_delay

                if CONF_DEVICE_STATES not in self.current_activity_data:
                    self.current_activity_data[CONF_DEVICE_STATES] = {}

                self.current_activity_data[CONF_DEVICE_STATES][self.selected_device_id] = device_config

                _LOGGER.info("Added device %s to activity", self.selected_device_id)
                self.selected_device_id = None  # Clear selection

                # Ask if user wants to add more devices
                return await self.async_step_device_menu()
            except Exception as ex:
                _LOGGER.exception("Error in add_device_details: %s", ex)
                errors["base"] = "unknown"

        # Get entity state
        state = self.hass.states.get(self.selected_device_id)
        friendly_name = state.attributes.get("friendly_name", self.selected_device_id) if state else self.selected_device_id

        # Build dynamic schema based on entity domain
        schema_dict = {}

        # Common field for all domains
        schema_dict[vol.Optional(CONF_POWER_ON_DELAY, default=DEFAULT_POWER_ON_DELAY)] = int

        # Domain-specific fields
        if domain == "media_player":
            # Get available sources
            source_list = state.attributes.get("source_list", []) if state else []

            if source_list:
                source_options = {"none": "-- No source selection --"}
                for source in source_list:
                    source_options[source] = source
            else:
                source_options = {"none": "-- Device has no sources --"}

            schema_dict[vol.Optional(CONF_INPUT_SOURCE, default="none")] = vol.In(source_options)
            schema_dict[vol.Optional(CONF_IS_VOLUME_CONTROLLER, default=False)] = bool
            schema_dict[vol.Optional(CONF_VOLUME_LEVEL, default=50)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

        elif domain == "light":
            schema_dict[vol.Optional(CONF_BRIGHTNESS, default=100)] = vol.All(
                int, vol.Range(min=0, max=100)
            )
            schema_dict[vol.Optional(CONF_COLOR_TEMP)] = vol.All(
                int, vol.Range(min=153, max=500)
            )
            schema_dict[vol.Optional(CONF_TRANSITION, default=0)] = vol.All(
                int, vol.Range(min=0, max=60)
            )

        elif domain == "cover":
            schema_dict[vol.Optional(CONF_POSITION, default=100)] = vol.All(
                int, vol.Range(min=0, max=100)
            )
            schema_dict[vol.Optional(CONF_TILT_POSITION)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

        # For switch, we only have the power_on_delay

        return self.async_show_form(
            step_id="add_device_details",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "device": friendly_name,
                "domain": domain,
                "room": self.current_room or "unknown",
                "activity": self.current_activity or "unknown",
            },
        )

    async def async_step_device_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask if user wants to add more devices."""
        if user_input is not None:
            try:
                action = user_input.get("action")

                if action == "add_device":
                    return await self.async_step_add_device()
                elif action == "edit_device":
                    return await self.async_step_select_device_to_edit()
                elif action == "delete_device":
                    return await self.async_step_select_device_to_delete()
                elif action == "reorder_device":
                    return await self.async_step_reorder_device()
                elif action == "finish_activity":
                    # Ensure device order is synchronized before saving
                    self._ensure_device_order(self.current_activity_data)

                    # Save activity
                    if self.current_room not in self.rooms:
                        _LOGGER.error("Room %s not found", self.current_room)
                        return await self.async_step_room_menu()

                    room_data = self.rooms[self.current_room]
                    if CONF_ACTIVITIES not in room_data:
                        room_data[CONF_ACTIVITIES] = {}

                    room_data[CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                    _LOGGER.info(
                        "Saved activity %s to room %s with %d devices",
                        self.current_activity,
                        self.current_room,
                        len(self.current_activity_data.get(CONF_DEVICE_STATES, {}))
                    )
                    # Save immediately
                    self._save_config()
                    return await self.async_step_activity_menu()
            except Exception as ex:
                _LOGGER.exception("Error in device_menu: %s", ex)
                return await self.async_step_room_menu()

        device_states = self.current_activity_data.get(CONF_DEVICE_STATES, {})

        # Ensure device order is synchronized
        device_order = self._ensure_device_order(self.current_activity_data)

        device_list = []
        for idx, entity_id in enumerate(device_order, 1):
            config = device_states.get(entity_id)
            if not config:
                continue
            domain = entity_id.split(".")[0]

            # Get friendly name
            state = self.hass.states.get(entity_id)
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id

            # Get power on delay
            delay = config.get(CONF_POWER_ON_DELAY, DEFAULT_POWER_ON_DELAY)

            info_parts = []

            # Media Player
            if domain == "media_player":
                source = config.get(CONF_INPUT_SOURCE)
                if source and source != "none":
                    info_parts.append(f"Source: {source}")
                if config.get(CONF_IS_VOLUME_CONTROLLER, False):
                    volume_level = config.get(CONF_VOLUME_LEVEL, 0.5)
                    volume_pct = int(volume_level * 100)
                    info_parts.append(f"Volume: {volume_pct}%")

            # Light
            elif domain == "light":
                brightness = config.get(CONF_BRIGHTNESS)
                if brightness is not None:
                    brightness_pct = int(brightness * 100 / 255)
                    info_parts.append(f"Brightness: {brightness_pct}%")
                color_temp = config.get(CONF_COLOR_TEMP)
                if color_temp is not None:
                    info_parts.append(f"Color Temp: {color_temp}K")
                transition = config.get(CONF_TRANSITION)
                if transition is not None and transition > 0:
                    info_parts.append(f"Transition: {transition}s")

            # Cover
            elif domain == "cover":
                position = config.get(CONF_POSITION)
                if position is not None:
                    info_parts.append(f"Position: {position}%")
                tilt = config.get(CONF_TILT_POSITION)
                if tilt is not None:
                    info_parts.append(f"Tilt: {tilt}%")

            # Switch
            elif domain == "switch":
                info_parts.append("On/Off")

            # Add delay information
            info_parts.append(f"Delay: {delay}s")

            # Build display string with order number and friendly name
            device_info = " [" + ", ".join(info_parts) + "]"
            device_list.append(f"{idx}. {friendly_name}{device_info}")

        device_list_str = "\n".join(device_list) if device_list else "No devices added yet"

        actions = {
            "add_device": "Add another device",
        }

        # Only show edit/delete/reorder if there are devices
        if device_states:
            actions["edit_device"] = "Edit device"
            actions["delete_device"] = "Delete device"
            # Only show reorder if there are 2+ devices
            if len(device_states) >= 2:
                actions["reorder_device"] = "Change device order"

        # Finish always at the bottom
        actions["finish_activity"] = "Finish activity"

        return self.async_show_form(
            step_id="device_menu",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(actions),
            }),
            description_placeholders={
                "devices": device_list_str,
            },
        )

    async def async_step_select_device_to_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a device to edit."""
        if user_input is not None:
            self.selected_device_id = user_input.get("device_id")
            _LOGGER.debug("Selected device to edit: %s", self.selected_device_id)
            return await self.async_step_edit_device()

        device_states = self.current_activity_data.get(CONF_DEVICE_STATES, {})

        if not device_states:
            return await self.async_step_device_menu()

        return self.async_show_form(
            step_id="select_device_to_edit",
            data_schema=vol.Schema({
                vol.Required("device_id"): vol.In(list(device_states.keys())),
            }),
        )

    async def async_step_edit_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit a device configuration."""
        errors = {}
        device_states = self.current_activity_data.get(CONF_DEVICE_STATES, {})

        # Get entity domain
        domain = self.selected_device_id.split(".")[0]

        # If user submitted the form
        if user_input is not None:
            try:
                device_config = {
                    CONF_POWER_ON_DELAY: user_input.get(
                        CONF_POWER_ON_DELAY, DEFAULT_POWER_ON_DELAY
                    ),
                }

                # Media player specific configuration
                if domain == "media_player":
                    input_source = user_input.get(CONF_INPUT_SOURCE)
                    if input_source and input_source.strip() and input_source != "none":
                        device_config[CONF_INPUT_SOURCE] = input_source.strip()

                    # Volume control settings
                    is_volume_controller = user_input.get(CONF_IS_VOLUME_CONTROLLER, False)
                    if is_volume_controller:
                        device_config[CONF_IS_VOLUME_CONTROLLER] = True
                        volume_level = user_input.get(CONF_VOLUME_LEVEL)
                        if volume_level is not None:
                            # Convert percentage to 0.0-1.0 range
                            device_config[CONF_VOLUME_LEVEL] = volume_level / 100.0

                # Light specific configuration
                elif domain == "light":
                    brightness = user_input.get(CONF_BRIGHTNESS)
                    if brightness is not None:
                        # Convert percentage to 0-255 range
                        device_config[CONF_BRIGHTNESS] = int(brightness * 255 / 100)

                    color_temp = user_input.get(CONF_COLOR_TEMP)
                    if color_temp is not None:
                        device_config[CONF_COLOR_TEMP] = color_temp

                    transition = user_input.get(CONF_TRANSITION)
                    if transition is not None:
                        device_config[CONF_TRANSITION] = transition

                # Cover specific configuration
                elif domain == "cover":
                    position = user_input.get(CONF_POSITION)
                    if position is not None:
                        device_config[CONF_POSITION] = position

                    tilt_position = user_input.get(CONF_TILT_POSITION)
                    if tilt_position is not None:
                        device_config[CONF_TILT_POSITION] = tilt_position

                # Switch has no additional configuration beyond power_on_delay

                device_states[self.selected_device_id] = device_config
                _LOGGER.info("Updated device %s", self.selected_device_id)

                # If we're editing an existing activity, save it
                if (self.current_room in self.rooms and
                    self.current_activity in self.rooms[self.current_room].get(CONF_ACTIVITIES, {})):
                    # Ensure device order is synchronized before saving
                    self._ensure_device_order(self.current_activity_data)
                    self.rooms[self.current_room][CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                    self._save_config()

                self.selected_device_id = None  # Clear selection
                return await self.async_step_device_menu()
            except Exception as ex:
                _LOGGER.exception("Error editing device: %s", ex)
                errors["base"] = "unknown"

        # Show edit form with current values
        if self.selected_device_id is None:
            _LOGGER.error("No device selected for editing")
            return await self.async_step_device_menu()

        current_config = device_states.get(self.selected_device_id, {})

        # Get entity state
        state = self.hass.states.get(self.selected_device_id)

        # Build dynamic schema based on entity domain
        schema_dict = {}

        # Common field for all domains
        schema_dict[vol.Optional(
            CONF_POWER_ON_DELAY,
            default=current_config.get(CONF_POWER_ON_DELAY, DEFAULT_POWER_ON_DELAY)
        )] = int

        # Domain-specific fields
        if domain == "media_player":
            # Convert volume from 0.0-1.0 to 0-100 for display
            current_volume = current_config.get(CONF_VOLUME_LEVEL, 0.5)
            if isinstance(current_volume, (int, float)):
                current_volume_pct = int(current_volume * 100)
            else:
                current_volume_pct = 50

            # Get available sources
            source_list = state.attributes.get("source_list", []) if state else []
            current_source = current_config.get(CONF_INPUT_SOURCE, "none")

            if source_list:
                source_options = {"none": "-- No source selection --"}
                for source in source_list:
                    source_options[source] = source
            else:
                source_options = {"none": "-- Device has no sources --"}

            # Make sure current source is in options
            if current_source and current_source != "none" and current_source not in source_options:
                source_options[current_source] = f"{current_source} (custom)"

            schema_dict[vol.Optional(
                CONF_INPUT_SOURCE,
                default=current_source if current_source else "none"
            )] = vol.In(source_options)
            schema_dict[vol.Optional(
                CONF_IS_VOLUME_CONTROLLER,
                default=current_config.get(CONF_IS_VOLUME_CONTROLLER, False)
            )] = bool
            schema_dict[vol.Optional(
                CONF_VOLUME_LEVEL,
                default=current_volume_pct
            )] = vol.All(int, vol.Range(min=0, max=100))

        elif domain == "light":
            # Convert brightness from 0-255 to 0-100 for display
            current_brightness = current_config.get(CONF_BRIGHTNESS, 255)
            if isinstance(current_brightness, (int, float)):
                current_brightness_pct = int(current_brightness * 100 / 255)
            else:
                current_brightness_pct = 100

            schema_dict[vol.Optional(
                CONF_BRIGHTNESS,
                default=current_brightness_pct
            )] = vol.All(int, vol.Range(min=0, max=100))

            if CONF_COLOR_TEMP in current_config:
                schema_dict[vol.Optional(
                    CONF_COLOR_TEMP,
                    default=current_config[CONF_COLOR_TEMP]
                )] = vol.All(int, vol.Range(min=153, max=500))
            else:
                schema_dict[vol.Optional(CONF_COLOR_TEMP)] = vol.All(
                    int, vol.Range(min=153, max=500)
                )

            schema_dict[vol.Optional(
                CONF_TRANSITION,
                default=current_config.get(CONF_TRANSITION, 0)
            )] = vol.All(int, vol.Range(min=0, max=60))

        elif domain == "cover":
            schema_dict[vol.Optional(
                CONF_POSITION,
                default=current_config.get(CONF_POSITION, 100)
            )] = vol.All(int, vol.Range(min=0, max=100))

            if CONF_TILT_POSITION in current_config:
                schema_dict[vol.Optional(
                    CONF_TILT_POSITION,
                    default=current_config[CONF_TILT_POSITION]
                )] = vol.All(int, vol.Range(min=0, max=100))
            else:
                schema_dict[vol.Optional(CONF_TILT_POSITION)] = vol.All(
                    int, vol.Range(min=0, max=100)
                )

        # For switch, we only have the power_on_delay

        return self.async_show_form(
            step_id="edit_device",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "device": self.selected_device_id,
                "domain": domain,
            },
        )

    async def async_step_select_device_to_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a device to delete."""
        if user_input is not None:
            device_id = user_input.get("device_id")

            device_states = self.current_activity_data.get(CONF_DEVICE_STATES, {})
            if device_id in device_states:
                del device_states[device_id]
                _LOGGER.info("Deleted device %s", device_id)

                # If we're editing an existing activity, save it
                if (self.current_room in self.rooms and
                    self.current_activity in self.rooms[self.current_room].get(CONF_ACTIVITIES, {})):
                    # Ensure device order is synchronized before saving (removes deleted device from order)
                    self._ensure_device_order(self.current_activity_data)
                    self.rooms[self.current_room][CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                    self._save_config()

            return await self.async_step_device_menu()

        device_states = self.current_activity_data.get(CONF_DEVICE_STATES, {})

        if not device_states:
            return await self.async_step_device_menu()

        return self.async_show_form(
            step_id="select_device_to_delete",
            data_schema=vol.Schema({
                vol.Required("device_id"): vol.In(list(device_states.keys())),
            }),
            description_placeholders={
                "warning": "This action cannot be undone!",
            },
        )

    async def async_step_reorder_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reorder devices in the activity."""
        device_states = self.current_activity_data.get(CONF_DEVICE_STATES, {})

        # Ensure device order is synchronized
        device_order = self._ensure_device_order(self.current_activity_data)

        if user_input is not None:
            device_id = user_input.get("device_id")
            direction = user_input.get("direction")

            # If done, return to device menu
            if direction == "done":
                return await self.async_step_device_menu()

            if device_id and direction:
                # Get current index from device_order
                current_index = device_order.index(device_id)

                # Calculate new index
                if direction == "up" and current_index > 0:
                    new_index = current_index - 1
                elif direction == "down" and current_index < len(device_order) - 1:
                    new_index = current_index + 1
                else:
                    # Can't move further, just return to menu
                    return await self.async_step_device_menu()

                # Swap positions in the device_order list
                device_order[current_index], device_order[new_index] = device_order[new_index], device_order[current_index]

                # Save the new order
                self.current_activity_data[CONF_DEVICE_ORDER] = device_order

                # If we're editing an existing activity, save it
                if (self.current_room in self.rooms and
                    self.current_activity in self.rooms[self.current_room].get(CONF_ACTIVITIES, {})):
                    self.rooms[self.current_room][CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                    self._save_config()

                _LOGGER.info("Moved device %s %s", device_id, direction)

            # Stay in reorder mode to allow multiple moves
            return await self.async_step_reorder_device()

        if not device_states or len(device_states) < 2:
            return await self.async_step_device_menu()

        # Build device selection with current order numbers
        device_options = {}
        for idx, entity_id in enumerate(device_order, 1):
            state = self.hass.states.get(entity_id)
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id
            device_options[entity_id] = f"{idx}. {friendly_name}"

        return self.async_show_form(
            step_id="reorder_device",
            data_schema=vol.Schema({
                vol.Required("device_id"): vol.In(device_options),
                vol.Required("direction"): vol.In({
                    "up": "Move up",
                    "down": "Move down",
                    "done": "Done reordering",
                }),
            }),
            description_placeholders={
                "info": "Select a device and choose whether to move it up or down in the order. Devices are executed from top to bottom when starting an activity.",
            },
        )
