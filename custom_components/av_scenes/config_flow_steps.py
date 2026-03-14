"""Steps management mixin for AV Scenes config flow."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ACTIVITIES,
    CONF_STEPS,
    CONF_STEP_ID,
    CONF_STEP_TYPE,
    CONF_STEP_DELAY_AFTER,
    CONF_STEP_PARAMETERS,
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

_LOGGER = logging.getLogger(__name__)


class StepsFlowMixin:
    """Mixin for step management flow steps."""

    async def async_step_step_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage steps for an activity."""
        if user_input is not None:
            try:
                action = user_input.get("action")

                if action == "add_step":
                    return await self.async_step_add_step()
                elif action == "edit_step":
                    return await self.async_step_select_step_to_edit()
                elif action == "delete_step":
                    return await self.async_step_select_step_to_delete()
                elif action == "reorder_step":
                    return await self.async_step_reorder_step()
                elif action == "finish_activity":
                    # Save activity
                    if self.current_room not in self.rooms:
                        _LOGGER.error("Room %s not found", self.current_room)
                        return await self.async_step_room_menu()

                    room_data = self.rooms[self.current_room]
                    if CONF_ACTIVITIES not in room_data:
                        room_data[CONF_ACTIVITIES] = {}

                    room_data[CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                    _LOGGER.info(
                        "Saved activity %s to room %s with %d steps",
                        self.current_activity,
                        self.current_room,
                        len(self.current_activity_data.get(CONF_STEPS, []))
                    )
                    # Save immediately
                    self._save_config()
                    return await self.async_step_activity_menu()
            except Exception as ex:
                _LOGGER.exception("Error in step_menu: %s", ex)
                return await self.async_step_room_menu()

        steps = self.current_activity_data.get(CONF_STEPS, [])

        _LOGGER.debug(
            "step_menu: current_activity_data has %d steps: %s",
            len(steps),
            [s.get(CONF_STEP_TYPE) for s in steps]
        )

        step_list = []
        for idx, step in enumerate(steps, 1):
            step_type = step.get(CONF_STEP_TYPE, "unknown")
            entity_id = step.get(CONF_ENTITY_ID, "")
            delay_after = step.get(CONF_STEP_DELAY_AFTER, 0)
            parameters = step.get(CONF_STEP_PARAMETERS, {})

            # Get friendly name
            state = self.hass.states.get(entity_id) if entity_id else None
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id

            # Build step description
            if step_type == STEP_TYPE_POWER_ON:
                step_desc = f"Turn on {friendly_name}"
            elif step_type == STEP_TYPE_SET_SOURCE:
                source = parameters.get(CONF_INPUT_SOURCE, "")
                step_desc = f"Set {friendly_name} source to '{source}'"
            elif step_type == STEP_TYPE_SET_VOLUME:
                volume_level = parameters.get(CONF_VOLUME_LEVEL, 0.5)
                volume_pct = int(volume_level * 100)
                step_desc = f"Set {friendly_name} volume to {volume_pct}%"
            elif step_type == STEP_TYPE_SET_SOUND_MODE:
                sound_mode = parameters.get(CONF_SOUND_MODE, "")
                step_desc = f"Set {friendly_name} sound mode to '{sound_mode}'"
            elif step_type == STEP_TYPE_SET_BRIGHTNESS:
                brightness = parameters.get(CONF_BRIGHTNESS)
                if brightness is not None:
                    brightness_pct = int(brightness * 100 / 255)
                    step_desc = f"Set {friendly_name} brightness to {brightness_pct}%"
                else:
                    step_desc = f"Configure {friendly_name}"
            elif step_type == STEP_TYPE_SET_COLOR_TEMP:
                color_temp = parameters.get(CONF_COLOR_TEMP, 0)
                step_desc = f"Set {friendly_name} color temp to {color_temp}K"
            elif step_type == STEP_TYPE_SET_POSITION:
                position = parameters.get(CONF_POSITION, 0)
                step_desc = f"Set {friendly_name} position to {position}%"
            elif step_type == STEP_TYPE_SET_TILT:
                tilt = parameters.get(CONF_TILT_POSITION, 0)
                step_desc = f"Set {friendly_name} tilt to {tilt}%"
            elif step_type == STEP_TYPE_CALL_ACTION:
                action = parameters.get(CONF_ACTION, "")
                step_desc = f"Call action: {action}"
            elif step_type == STEP_TYPE_DELAY:
                step_desc = f"Wait {delay_after} seconds"
            else:
                step_desc = f"{step_type} on {friendly_name}"

            # Add delay information if > 0
            if delay_after > 0 and step_type != STEP_TYPE_DELAY:
                step_desc += f" (then wait {delay_after}s)"

            step_list.append(f"{idx}. {step_desc}")

        step_list_str = "\n".join(step_list) if step_list else "No steps added yet"

        actions = {
            "add_step": "Add step",
        }

        # Only show edit/delete/reorder if there are steps
        if steps:
            actions["edit_step"] = "Edit step"
            actions["delete_step"] = "Delete step"
            # Only show reorder if there are 2+ steps
            if len(steps) >= 2:
                actions["reorder_step"] = "Change step order"

        # Finish always at the bottom
        actions["finish_activity"] = "Finish activity"

        return self.async_show_form(
            step_id="step_menu",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(actions),
            }),
            description_placeholders={
                "steps": step_list_str,
            },
        )

    async def async_step_add_step(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a step - select step type."""
        errors = {}

        if user_input is not None:
            try:
                step_type = user_input.get(CONF_STEP_TYPE)
                self.current_step_data = {
                    CONF_STEP_ID: str(uuid.uuid4()),
                    CONF_STEP_TYPE: step_type,
                    CONF_STEP_DELAY_AFTER: 0,
                    CONF_STEP_PARAMETERS: {},
                }

                # If step type is DELAY or CALL_ACTION, we don't need entity selection
                if step_type == STEP_TYPE_DELAY:
                    return await self.async_step_add_step_delay_config()
                elif step_type == STEP_TYPE_CALL_ACTION:
                    return await self.async_step_add_step_action_config()
                else:
                    return await self.async_step_add_step_entity()
            except Exception as ex:
                _LOGGER.exception("Error in add_step: %s", ex)
                errors["base"] = "unknown"

        # Build step type options with descriptions
        step_types = {
            STEP_TYPE_POWER_ON: "Turn on device",
            STEP_TYPE_SET_SOURCE: "Set input source (media player)",
            STEP_TYPE_SET_VOLUME: "Set volume (media player)",
            STEP_TYPE_SET_SOUND_MODE: "Set sound mode (media player)",
            STEP_TYPE_SET_BRIGHTNESS: "Set brightness/color (light)",
            STEP_TYPE_SET_COLOR_TEMP: "Set color temperature (light)",
            STEP_TYPE_SET_POSITION: "Set position (cover)",
            STEP_TYPE_SET_TILT: "Set tilt (cover)",
            STEP_TYPE_CALL_ACTION: "Call action",
            STEP_TYPE_DELAY: "Wait/Delay",
        }

        return self.async_show_form(
            step_id="add_step",
            data_schema=vol.Schema({
                vol.Required(CONF_STEP_TYPE): vol.In(step_types),
            }),
            errors=errors,
            description_placeholders={
                "info": "Select the type of step to add. Steps are executed in order.",
            },
        )

    async def async_step_add_step_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select entity for the step."""
        errors = {}

        if user_input is not None:
            try:
                entity_id = user_input.get(CONF_ENTITY_ID)

                # Validate entity exists
                state = self.hass.states.get(entity_id)
                if state is None:
                    errors[CONF_ENTITY_ID] = "entity_not_found"
                else:
                    self.current_step_data[CONF_ENTITY_ID] = entity_id
                    return await self.async_step_add_step_config()
            except Exception as ex:
                _LOGGER.exception("Error in add_step_entity: %s", ex)
                errors["base"] = "unknown"

        # Get step type to filter entities
        step_type = self.current_step_data.get(CONF_STEP_TYPE)

        # Determine which domains to show based on step type
        if step_type in [STEP_TYPE_SET_SOURCE, STEP_TYPE_SET_VOLUME, STEP_TYPE_SET_SOUND_MODE]:
            supported_domains = ["media_player"]
        elif step_type in [STEP_TYPE_SET_BRIGHTNESS, STEP_TYPE_SET_COLOR_TEMP]:
            supported_domains = ["light"]
        elif step_type in [STEP_TYPE_SET_POSITION, STEP_TYPE_SET_TILT]:
            supported_domains = ["cover"]
        else:  # POWER_ON and others
            supported_domains = ["media_player", "light", "switch", "cover"]

        entities = []
        for domain in supported_domains:
            for entity_id in self.hass.states.async_entity_ids(domain):
                state = self.hass.states.get(entity_id)
                if state:
                    friendly_name = state.attributes.get("friendly_name", entity_id)
                    display_name = f"[{domain}] {friendly_name}"
                    entities.append((entity_id, display_name))

        # Sort by display name
        entities.sort(key=lambda x: x[1])

        # Create entity selector options
        entity_options = {entity_id: name for entity_id, name in entities}

        if not entity_options:
            entity_options = {"": "No entities found"}

        return self.async_show_form(
            step_id="add_step_entity",
            data_schema=vol.Schema({
                vol.Required(CONF_ENTITY_ID): vol.In(entity_options),
            }),
            errors=errors,
            description_placeholders={
                "step_type": step_type,
            },
        )

    async def async_step_add_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure step parameters."""
        errors = {}

        step_type = self.current_step_data.get(CONF_STEP_TYPE)
        entity_id = self.current_step_data.get(CONF_ENTITY_ID)

        if user_input is not None:
            try:
                # Get delay_after
                delay_after = user_input.get(CONF_STEP_DELAY_AFTER, 0)
                self.current_step_data[CONF_STEP_DELAY_AFTER] = delay_after

                # Get step-specific parameters
                parameters = {}

                if step_type == STEP_TYPE_SET_SOURCE:
                    source = user_input.get(CONF_INPUT_SOURCE)
                    if source and source != "none":
                        parameters[CONF_INPUT_SOURCE] = source

                elif step_type == STEP_TYPE_SET_VOLUME:
                    volume_level = user_input.get(CONF_VOLUME_LEVEL, 50)
                    parameters[CONF_VOLUME_LEVEL] = volume_level / 100.0

                elif step_type == STEP_TYPE_SET_SOUND_MODE:
                    sound_mode = user_input.get(CONF_SOUND_MODE)
                    if sound_mode and sound_mode != "none":
                        parameters[CONF_SOUND_MODE] = sound_mode

                elif step_type == STEP_TYPE_SET_BRIGHTNESS:
                    brightness = user_input.get(CONF_BRIGHTNESS)
                    if brightness is not None:
                        parameters[CONF_BRIGHTNESS] = int(brightness * 255 / 100)

                    color_temp = user_input.get(CONF_COLOR_TEMP)
                    if color_temp is not None:
                        parameters[CONF_COLOR_TEMP] = color_temp

                    transition = user_input.get(CONF_TRANSITION)
                    if transition is not None:
                        parameters[CONF_TRANSITION] = transition

                elif step_type == STEP_TYPE_SET_COLOR_TEMP:
                    color_temp = user_input.get(CONF_COLOR_TEMP)
                    if color_temp is not None:
                        parameters[CONF_COLOR_TEMP] = color_temp

                elif step_type == STEP_TYPE_SET_POSITION:
                    position = user_input.get(CONF_POSITION)
                    if position is not None:
                        parameters[CONF_POSITION] = position

                elif step_type == STEP_TYPE_SET_TILT:
                    tilt = user_input.get(CONF_TILT_POSITION)
                    if tilt is not None:
                        parameters[CONF_TILT_POSITION] = tilt

                self.current_step_data[CONF_STEP_PARAMETERS] = parameters

                # Add step to activity
                if CONF_STEPS not in self.current_activity_data:
                    self.current_activity_data[CONF_STEPS] = []

                self.current_activity_data[CONF_STEPS].append(self.current_step_data)
                _LOGGER.info(
                    "Added step %s (type: %s, entity: %s) to activity. Total steps: %d",
                    self.current_step_data[CONF_STEP_ID],
                    step_type,
                    entity_id,
                    len(self.current_activity_data[CONF_STEPS])
                )

                return await self.async_step_step_menu()
            except Exception as ex:
                _LOGGER.exception("Error in add_step_config: %s", ex)
                errors["base"] = "unknown"

        # Get entity state for source list etc.
        state = self.hass.states.get(entity_id)
        friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id

        # Build dynamic schema based on step type
        schema_dict = {}

        # Common field for delay
        schema_dict[vol.Optional(CONF_STEP_DELAY_AFTER, default=0)] = vol.All(
            int, vol.Range(min=0, max=60)
        )

        # Step-specific fields
        if step_type == STEP_TYPE_POWER_ON:
            # No additional parameters for power on
            pass

        elif step_type == STEP_TYPE_SET_SOURCE:
            source_list = state.attributes.get("source_list", []) if state else []

            if source_list:
                source_options = {"none": "-- Select source --"}
                for source in source_list:
                    source_options[source] = source
            else:
                source_options = {"none": "-- Device has no sources --"}

            schema_dict[vol.Required(CONF_INPUT_SOURCE, default="none")] = vol.In(source_options)

        elif step_type == STEP_TYPE_SET_VOLUME:
            schema_dict[vol.Required(CONF_VOLUME_LEVEL, default=50)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

        elif step_type == STEP_TYPE_SET_SOUND_MODE:
            sound_mode_list = state.attributes.get("sound_mode_list", []) if state else []

            if sound_mode_list:
                sound_mode_options = {"none": "-- Select sound mode --"}
                for mode in sound_mode_list:
                    sound_mode_options[mode] = mode
            else:
                sound_mode_options = {"none": "-- Device has no sound modes --"}

            schema_dict[vol.Required(CONF_SOUND_MODE, default="none")] = vol.In(sound_mode_options)

        elif step_type == STEP_TYPE_SET_BRIGHTNESS:
            schema_dict[vol.Optional(CONF_BRIGHTNESS, default=100)] = vol.All(
                int, vol.Range(min=0, max=100)
            )
            schema_dict[vol.Optional(CONF_COLOR_TEMP)] = vol.All(
                int, vol.Range(min=153, max=500)
            )
            schema_dict[vol.Optional(CONF_TRANSITION, default=0)] = vol.All(
                int, vol.Range(min=0, max=60)
            )

        elif step_type == STEP_TYPE_SET_COLOR_TEMP:
            schema_dict[vol.Required(CONF_COLOR_TEMP, default=250)] = vol.All(
                int, vol.Range(min=153, max=500)
            )

        elif step_type == STEP_TYPE_SET_POSITION:
            schema_dict[vol.Required(CONF_POSITION, default=100)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

        elif step_type == STEP_TYPE_SET_TILT:
            schema_dict[vol.Required(CONF_TILT_POSITION, default=50)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

        return self.async_show_form(
            step_id="add_step_config",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "device": friendly_name,
                "step_type": step_type,
                "info": "Configure the parameters for this step. The delay is applied AFTER this step completes.",
            },
        )

    async def async_step_add_step_delay_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure delay step."""
        errors = {}

        if user_input is not None:
            try:
                delay = user_input.get(CONF_STEP_DELAY_AFTER, 1)
                self.current_step_data[CONF_STEP_DELAY_AFTER] = delay
                self.current_step_data[CONF_ENTITY_ID] = ""  # No entity for delay

                # Add step to activity
                if CONF_STEPS not in self.current_activity_data:
                    self.current_activity_data[CONF_STEPS] = []

                self.current_activity_data[CONF_STEPS].append(self.current_step_data)
                _LOGGER.info(
                    "Added delay step of %d seconds. Total steps: %d",
                    delay,
                    len(self.current_activity_data[CONF_STEPS])
                )

                return await self.async_step_step_menu()
            except Exception as ex:
                _LOGGER.exception("Error in add_step_delay_config: %s", ex)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="add_step_delay_config",
            data_schema=vol.Schema({
                vol.Required(CONF_STEP_DELAY_AFTER, default=1): vol.All(
                    int, vol.Range(min=1, max=60)
                ),
            }),
            errors=errors,
            description_placeholders={
                "info": "How long should the system wait (in seconds)?",
            },
        )

    async def async_step_add_step_action_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure action call step."""
        errors = {}

        if user_input is not None:
            try:
                action = user_input.get(CONF_ACTION, "")
                service_data = user_input.get(CONF_SERVICE_DATA, "")
                delay_after = user_input.get(CONF_STEP_DELAY_AFTER, 0)

                if not action:
                    errors[CONF_ACTION] = "invalid_name"
                else:
                    self.current_step_data[CONF_ENTITY_ID] = ""  # No entity for action call
                    self.current_step_data[CONF_STEP_DELAY_AFTER] = delay_after

                    parameters = {
                        CONF_ACTION: action,
                    }

                    # Parse service_data if provided
                    if service_data:
                        try:
                            import json
                            data = json.loads(service_data)
                            parameters[CONF_SERVICE_DATA] = data
                        except json.JSONDecodeError:
                            errors[CONF_SERVICE_DATA] = "invalid_name"
                            _LOGGER.error("Invalid JSON in service_data: %s", service_data)

                    if not errors:
                        self.current_step_data[CONF_STEP_PARAMETERS] = parameters

                        # Add step to activity
                        if CONF_STEPS not in self.current_activity_data:
                            self.current_activity_data[CONF_STEPS] = []

                        self.current_activity_data[CONF_STEPS].append(self.current_step_data)
                        _LOGGER.info(
                            "Added action call step: %s. Total steps: %d",
                            action,
                            len(self.current_activity_data[CONF_STEPS])
                        )

                        return await self.async_step_step_menu()
            except Exception as ex:
                _LOGGER.exception("Error in add_step_action_config: %s", ex)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="add_step_action_config",
            data_schema=vol.Schema({
                vol.Required(CONF_ACTION): str,
                vol.Optional(CONF_SERVICE_DATA): str,
                vol.Optional(CONF_STEP_DELAY_AFTER, default=0): vol.All(
                    int, vol.Range(min=0, max=60)
                ),
            }),
            errors=errors,
            description_placeholders={
                "info": "Call any Home Assistant action. Format: domain.service (e.g., light.turn_on). Service data should be valid JSON.",
            },
        )

    async def async_step_reorder_step(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reorder steps in the activity."""
        steps = self.current_activity_data.get(CONF_STEPS, [])

        if user_input is not None:
            step_id = user_input.get("step_id")
            direction = user_input.get("direction")

            # If done, return to step menu
            if direction == "done":
                # Save if editing existing activity
                if (self.current_room in self.rooms and
                    self.current_activity in self.rooms[self.current_room].get(CONF_ACTIVITIES, {})):
                    self.rooms[self.current_room][CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                    self._save_config()
                return await self.async_step_step_menu()

            if step_id and direction:
                # Find step index
                current_index = None
                for idx, step in enumerate(steps):
                    if step.get(CONF_STEP_ID) == step_id:
                        current_index = idx
                        break

                if current_index is not None:
                    # Calculate new index
                    if direction == "up" and current_index > 0:
                        new_index = current_index - 1
                    elif direction == "down" and current_index < len(steps) - 1:
                        new_index = current_index + 1
                    else:
                        # Can't move further
                        return await self.async_step_reorder_step()

                    # Swap positions
                    steps[current_index], steps[new_index] = steps[new_index], steps[current_index]

                    # Save if editing existing activity
                    if (self.current_room in self.rooms and
                        self.current_activity in self.rooms[self.current_room].get(CONF_ACTIVITIES, {})):
                        self.rooms[self.current_room][CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                        self._save_config()

                    _LOGGER.info("Moved step %s", direction)

            # Stay in reorder mode to allow multiple moves
            return await self.async_step_reorder_step()

        if not steps or len(steps) < 2:
            return await self.async_step_step_menu()

        # Build step selection with current order numbers
        step_options = {}
        for idx, step in enumerate(steps, 1):
            step_id = step.get(CONF_STEP_ID)
            step_type = step.get(CONF_STEP_TYPE, "unknown")
            entity_id = step.get(CONF_ENTITY_ID, "")
            parameters = step.get(CONF_STEP_PARAMETERS, {})

            # Get friendly name
            state = self.hass.states.get(entity_id) if entity_id else None
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else "Delay"

            # Build short description
            if step_type == STEP_TYPE_POWER_ON:
                desc = f"Turn on {friendly_name}"
            elif step_type == STEP_TYPE_SET_SOURCE:
                source = parameters.get(CONF_INPUT_SOURCE, "")
                desc = f"{friendly_name} → {source}"
            elif step_type == STEP_TYPE_SET_SOUND_MODE:
                sound_mode = parameters.get(CONF_SOUND_MODE, "")
                desc = f"{friendly_name} → {sound_mode}"
            elif step_type == STEP_TYPE_CALL_ACTION:
                action = parameters.get(CONF_ACTION, "")
                desc = f"Call: {action}"
            elif step_type == STEP_TYPE_DELAY:
                delay = step.get(CONF_STEP_DELAY_AFTER, 0)
                desc = f"Wait {delay}s"
            else:
                desc = f"{step_type} {friendly_name}"

            step_options[step_id] = f"{idx}. {desc}"

        return self.async_show_form(
            step_id="reorder_step",
            data_schema=vol.Schema({
                vol.Required("step_id"): vol.In(step_options),
                vol.Required("direction"): vol.In({
                    "up": "Move up",
                    "down": "Move down",
                    "done": "Done reordering",
                }),
            }),
            description_placeholders={
                "info": "Select a step and choose whether to move it up or down. Steps are executed from top to bottom.",
            },
        )

    async def async_step_select_step_to_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a step to delete."""
        if user_input is not None:
            step_id = user_input.get("step_id")

            steps = self.current_activity_data.get(CONF_STEPS, [])
            # Find and remove step
            self.current_activity_data[CONF_STEPS] = [s for s in steps if s.get(CONF_STEP_ID) != step_id]
            _LOGGER.info("Deleted step %s", step_id)

            # Save if editing existing activity
            if (self.current_room in self.rooms and
                self.current_activity in self.rooms[self.current_room].get(CONF_ACTIVITIES, {})):
                self.rooms[self.current_room][CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                self._save_config()

            return await self.async_step_step_menu()

        steps = self.current_activity_data.get(CONF_STEPS, [])

        if not steps:
            return await self.async_step_step_menu()

        # Build step selection
        step_options = {}
        for idx, step in enumerate(steps, 1):
            step_id = step.get(CONF_STEP_ID)
            step_type = step.get(CONF_STEP_TYPE, "unknown")
            entity_id = step.get(CONF_ENTITY_ID, "")

            state = self.hass.states.get(entity_id) if entity_id else None
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else "Delay"

            desc = f"{idx}. {step_type} - {friendly_name}"
            step_options[step_id] = desc

        return self.async_show_form(
            step_id="select_step_to_delete",
            data_schema=vol.Schema({
                vol.Required("step_id"): vol.In(step_options),
            }),
            description_placeholders={
                "warning": "This action cannot be undone!",
            },
        )

    async def async_step_select_step_to_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a step to edit."""
        if user_input is not None:
            self.selected_step_id = user_input.get("step_id")
            _LOGGER.debug("Selected step to edit: %s", self.selected_step_id)
            return await self.async_step_edit_step()

        steps = self.current_activity_data.get(CONF_STEPS, [])

        if not steps:
            return await self.async_step_step_menu()

        # Build step selection
        step_options = {}
        for idx, step in enumerate(steps, 1):
            step_id = step.get(CONF_STEP_ID)
            step_type = step.get(CONF_STEP_TYPE, "unknown")
            entity_id = step.get(CONF_ENTITY_ID, "")

            state = self.hass.states.get(entity_id) if entity_id else None
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else "Delay"

            desc = f"{idx}. {step_type} - {friendly_name}"
            step_options[step_id] = desc

        return self.async_show_form(
            step_id="select_step_to_edit",
            data_schema=vol.Schema({
                vol.Required("step_id"): vol.In(step_options),
            }),
            description_placeholders={
                "info": "Choose a step to edit",
            },
        )

    async def async_step_edit_step(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit a step configuration."""
        errors = {}
        steps = self.current_activity_data.get(CONF_STEPS, [])

        # Find the step to edit
        current_step = None
        for step in steps:
            if step.get(CONF_STEP_ID) == self.selected_step_id:
                current_step = step
                break

        if not current_step:
            _LOGGER.error("Step %s not found", self.selected_step_id)
            return await self.async_step_step_menu()

        step_type = current_step.get(CONF_STEP_TYPE)
        entity_id = current_step.get(CONF_ENTITY_ID, "")

        if user_input is not None:
            try:
                # Update delay_after
                delay_after = user_input.get(CONF_STEP_DELAY_AFTER, 0)
                current_step[CONF_STEP_DELAY_AFTER] = delay_after

                # Update step-specific parameters
                parameters = {}

                if step_type == STEP_TYPE_SET_SOURCE:
                    source = user_input.get(CONF_INPUT_SOURCE)
                    if source and source != "none":
                        parameters[CONF_INPUT_SOURCE] = source

                elif step_type == STEP_TYPE_SET_VOLUME:
                    volume_level = user_input.get(CONF_VOLUME_LEVEL, 50)
                    parameters[CONF_VOLUME_LEVEL] = volume_level / 100.0

                elif step_type == STEP_TYPE_SET_SOUND_MODE:
                    sound_mode = user_input.get(CONF_SOUND_MODE)
                    if sound_mode and sound_mode != "none":
                        parameters[CONF_SOUND_MODE] = sound_mode

                elif step_type == STEP_TYPE_SET_BRIGHTNESS:
                    brightness = user_input.get(CONF_BRIGHTNESS)
                    if brightness is not None:
                        parameters[CONF_BRIGHTNESS] = int(brightness * 255 / 100)

                    color_temp = user_input.get(CONF_COLOR_TEMP)
                    if color_temp is not None:
                        parameters[CONF_COLOR_TEMP] = color_temp

                    transition = user_input.get(CONF_TRANSITION)
                    if transition is not None:
                        parameters[CONF_TRANSITION] = transition

                elif step_type == STEP_TYPE_SET_COLOR_TEMP:
                    color_temp = user_input.get(CONF_COLOR_TEMP)
                    if color_temp is not None:
                        parameters[CONF_COLOR_TEMP] = color_temp

                elif step_type == STEP_TYPE_SET_POSITION:
                    position = user_input.get(CONF_POSITION)
                    if position is not None:
                        parameters[CONF_POSITION] = position

                elif step_type == STEP_TYPE_SET_TILT:
                    tilt = user_input.get(CONF_TILT_POSITION)
                    if tilt is not None:
                        parameters[CONF_TILT_POSITION] = tilt

                elif step_type == STEP_TYPE_CALL_ACTION:
                    action = user_input.get(CONF_ACTION, "")
                    service_data = user_input.get(CONF_SERVICE_DATA, "")

                    if action:
                        parameters[CONF_ACTION] = action

                    if service_data:
                        try:
                            import json
                            data = json.loads(service_data)
                            parameters[CONF_SERVICE_DATA] = data
                        except json.JSONDecodeError:
                            _LOGGER.error("Invalid JSON in service_data: %s", service_data)

                elif step_type == STEP_TYPE_DELAY:
                    # For delay steps, the delay is in delay_after
                    pass

                current_step[CONF_STEP_PARAMETERS] = parameters

                _LOGGER.info("Updated step %s", self.selected_step_id)

                # Save if editing existing activity
                if (self.current_room in self.rooms and
                    self.current_activity in self.rooms[self.current_room].get(CONF_ACTIVITIES, {})):
                    self.rooms[self.current_room][CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                    self._save_config()

                self.selected_step_id = None  # Clear selection
                return await self.async_step_step_menu()
            except Exception as ex:
                _LOGGER.exception("Error editing step: %s", ex)
                errors["base"] = "unknown"

        # Get entity state for source list etc.
        state = self.hass.states.get(entity_id) if entity_id else None
        friendly_name = state.attributes.get("friendly_name", entity_id) if state else "Delay"

        # Build dynamic schema based on step type with current values
        schema_dict = {}

        # Get current parameters
        current_params = current_step.get(CONF_STEP_PARAMETERS, {})
        current_delay = current_step.get(CONF_STEP_DELAY_AFTER, 0)

        # Common field for delay
        if step_type == STEP_TYPE_DELAY:
            # For delay steps, the delay is the main config
            schema_dict[vol.Required(CONF_STEP_DELAY_AFTER, default=current_delay)] = vol.All(
                int, vol.Range(min=1, max=60)
            )
        else:
            schema_dict[vol.Optional(CONF_STEP_DELAY_AFTER, default=current_delay)] = vol.All(
                int, vol.Range(min=0, max=60)
            )

        # Step-specific fields with current values
        if step_type == STEP_TYPE_POWER_ON:
            # No additional parameters for power on
            pass

        elif step_type == STEP_TYPE_SET_SOURCE:
            source_list = state.attributes.get("source_list", []) if state else []
            current_source = current_params.get(CONF_INPUT_SOURCE, "none")

            if source_list:
                source_options = {"none": "-- Select source --"}
                for source in source_list:
                    source_options[source] = source
            else:
                source_options = {"none": "-- Device has no sources --"}

            # Make sure current source is in options
            if current_source and current_source != "none" and current_source not in source_options:
                source_options[current_source] = f"{current_source} (current)"

            schema_dict[vol.Required(CONF_INPUT_SOURCE, default=current_source)] = vol.In(source_options)

        elif step_type == STEP_TYPE_SET_VOLUME:
            current_volume = current_params.get(CONF_VOLUME_LEVEL, 0.5)
            current_volume_pct = int(current_volume * 100)

            schema_dict[vol.Required(CONF_VOLUME_LEVEL, default=current_volume_pct)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

        elif step_type == STEP_TYPE_SET_SOUND_MODE:
            sound_mode_list = state.attributes.get("sound_mode_list", []) if state else []
            current_sound_mode = current_params.get(CONF_SOUND_MODE, "none")

            if sound_mode_list:
                sound_mode_options = {"none": "-- Select sound mode --"}
                for mode in sound_mode_list:
                    sound_mode_options[mode] = mode
            else:
                sound_mode_options = {"none": "-- Device has no sound modes --"}

            # Make sure current sound mode is in options
            if current_sound_mode and current_sound_mode != "none" and current_sound_mode not in sound_mode_options:
                sound_mode_options[current_sound_mode] = f"{current_sound_mode} (current)"

            schema_dict[vol.Required(CONF_SOUND_MODE, default=current_sound_mode)] = vol.In(sound_mode_options)

        elif step_type == STEP_TYPE_SET_BRIGHTNESS:
            current_brightness = current_params.get(CONF_BRIGHTNESS)
            if current_brightness is not None:
                current_brightness_pct = int(current_brightness * 100 / 255)
            else:
                current_brightness_pct = 100

            schema_dict[vol.Optional(CONF_BRIGHTNESS, default=current_brightness_pct)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

            current_color_temp = current_params.get(CONF_COLOR_TEMP)
            if current_color_temp is not None:
                schema_dict[vol.Optional(CONF_COLOR_TEMP, default=current_color_temp)] = vol.All(
                    int, vol.Range(min=153, max=500)
                )
            else:
                schema_dict[vol.Optional(CONF_COLOR_TEMP)] = vol.All(
                    int, vol.Range(min=153, max=500)
                )

            current_transition = current_params.get(CONF_TRANSITION, 0)
            schema_dict[vol.Optional(CONF_TRANSITION, default=current_transition)] = vol.All(
                int, vol.Range(min=0, max=60)
            )

        elif step_type == STEP_TYPE_SET_COLOR_TEMP:
            current_color_temp = current_params.get(CONF_COLOR_TEMP, 250)
            schema_dict[vol.Required(CONF_COLOR_TEMP, default=current_color_temp)] = vol.All(
                int, vol.Range(min=153, max=500)
            )

        elif step_type == STEP_TYPE_SET_POSITION:
            current_position = current_params.get(CONF_POSITION, 100)
            schema_dict[vol.Required(CONF_POSITION, default=current_position)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

        elif step_type == STEP_TYPE_SET_TILT:
            current_tilt = current_params.get(CONF_TILT_POSITION, 50)
            schema_dict[vol.Required(CONF_TILT_POSITION, default=current_tilt)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

        elif step_type == STEP_TYPE_CALL_ACTION:
            current_action = current_params.get(CONF_ACTION, "")
            current_service_data = current_params.get(CONF_SERVICE_DATA, {})

            # Convert service_data dict to JSON string for editing
            import json
            service_data_str = json.dumps(current_service_data) if current_service_data else ""

            schema_dict[vol.Required(CONF_ACTION, default=current_action)] = str
            schema_dict[vol.Optional(CONF_SERVICE_DATA, default=service_data_str)] = str
            friendly_name = f"Action: {current_action}"

        return self.async_show_form(
            step_id="edit_step",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "device": friendly_name,
                "step_type": step_type,
                "info": "Edit the parameters for this step.",
            },
        )
