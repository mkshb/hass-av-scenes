"""Activities management mixin for AV Scenes config flow."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ACTIVITIES,
    CONF_ACTIVITY_NAME,
    CONF_STEPS,
    CONF_STEP_TYPE,
    CONF_ENTITY_ID,
    CONF_STEP_DELAY_AFTER,
    CONF_STEP_PARAMETERS,
    CONF_INPUT_SOURCE,
    CONF_VOLUME_LEVEL,
    CONF_SOUND_MODE,
    CONF_BRIGHTNESS,
    CONF_COLOR_TEMP,
    CONF_POSITION,
    CONF_TILT_POSITION,
    CONF_ACTION,
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


class ActivitiesFlowMixin:
    """Mixin for activity management flow steps."""

    async def async_step_activity_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage activities for a room."""
        _LOGGER.debug(
            "Options flow: activity_menu called for room %s with input: %s",
            self.current_room,
            user_input
        )

        if user_input is not None:
            action = user_input.get("action")

            if action == "add_activity":
                return await self.async_step_add_activity()
            elif action == "edit_activity":
                return await self.async_step_select_activity()
            elif action == "delete_activity":
                return await self.async_step_delete_activity()
            elif action == "copy_activity":
                return await self.async_step_copy_activity()
            elif action == "back":
                return await self.async_step_room_menu()

        room_data = self.rooms[self.current_room]
        activities = room_data.get(CONF_ACTIVITIES, {})
        activity_list = "\n".join([f"- {act_name}" for act_name in activities.keys()])
        if not activity_list:
            activity_list = "No activities configured yet"

        actions = {
            "add_activity": "Add new activity",
        }

        # Only show edit/delete/copy if there are activities
        if activities:
            actions["edit_activity"] = "Edit existing activity"
            actions["delete_activity"] = "Delete activity"
            actions["copy_activity"] = "Copy activity"

        # Back always at the bottom
        actions["back"] = "Back to room menu"

        return self.async_show_form(
            step_id="activity_menu",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(actions),
            }),
            description_placeholders={
                "room": self.current_room,
                "activities": activity_list,
            },
        )

    async def async_step_add_activity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new activity."""
        errors = {}

        if user_input is not None:
            try:
                activity_name = user_input.get(CONF_ACTIVITY_NAME)

                if not activity_name or not activity_name.strip():
                    errors[CONF_ACTIVITY_NAME] = "invalid_name"
                elif self.current_room not in self.rooms:
                    errors["base"] = "room_not_found"
                else:
                    room_data = self.rooms[self.current_room]

                    if CONF_ACTIVITIES not in room_data:
                        room_data[CONF_ACTIVITIES] = {}

                    if activity_name in room_data[CONF_ACTIVITIES]:
                        errors[CONF_ACTIVITY_NAME] = "already_exists"
                    else:
                        self.current_activity = activity_name
                        self.current_activity_data = {
                            CONF_STEPS: []
                        }
                        return await self.async_step_step_menu()
            except Exception as ex:
                _LOGGER.exception("Error in add_activity: %s", ex)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="add_activity",
            data_schema=vol.Schema({
                vol.Required(CONF_ACTIVITY_NAME): str,
            }),
            errors=errors,
            description_placeholders={
                "room": self.current_room or "unknown",
            },
        )

    async def async_step_select_activity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select an activity to edit."""
        if user_input is not None:
            self.current_activity = user_input.get("activity_name")
            return await self.async_step_edit_activity()

        room_data = self.rooms.get(self.current_room, {})
        activities = room_data.get(CONF_ACTIVITIES, {})

        if not activities:
            return await self.async_step_activity_menu()

        return self.async_show_form(
            step_id="select_activity",
            data_schema=vol.Schema({
                vol.Required("activity_name"): vol.In(list(activities.keys())),
            }),
            description_placeholders={
                "room": self.current_room or "unknown",
            },
        )

    async def async_step_edit_activity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit an existing activity."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "edit_steps":
                # Load existing activity data
                room_data = self.rooms[self.current_room]
                self.current_activity_data = room_data[CONF_ACTIVITIES][self.current_activity]
                return await self.async_step_step_menu()
            elif action == "rename":
                return await self.async_step_rename_activity()
            elif action == "back":
                return await self.async_step_activity_menu()

        # Show current steps
        room_data = self.rooms.get(self.current_room, {})
        activity_data = room_data.get(CONF_ACTIVITIES, {}).get(self.current_activity, {})
        steps = activity_data.get(CONF_STEPS, [])

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

        step_list_str = "\n".join(step_list) if step_list else "No steps configured"

        return self.async_show_form(
            step_id="edit_activity",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In({
                    "edit_steps": "Edit steps",
                    "rename": "Rename activity",
                    "back": "Back",
                }),
            }),
            description_placeholders={
                "activity": self.current_activity or "unknown",
                "steps": step_list_str,
            },
        )

    async def async_step_rename_activity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Rename an activity."""
        errors = {}

        if user_input is not None:
            new_name = user_input.get("new_name")

            if not new_name or not new_name.strip():
                errors["new_name"] = "invalid_name"
            elif new_name == self.current_activity:
                # No change, go back
                return await self.async_step_edit_activity()
            else:
                room_data = self.rooms[self.current_room]
                activities = room_data[CONF_ACTIVITIES]

                if new_name in activities:
                    errors["new_name"] = "already_exists"
                else:
                    # Rename by copying and deleting old
                    activities[new_name] = activities[self.current_activity]
                    del activities[self.current_activity]
                    self.current_activity = new_name
                    _LOGGER.info("Renamed activity to %s", new_name)
                    # Save immediately
                    self._save_config()
                    return await self.async_step_activity_menu()

        return self.async_show_form(
            step_id="rename_activity",
            data_schema=vol.Schema({
                vol.Required("new_name", default=self.current_activity): str,
            }),
            errors=errors,
            description_placeholders={
                "old_name": self.current_activity or "unknown",
            },
        )

    async def async_step_delete_activity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Delete an activity."""
        if user_input is not None:
            activity_to_delete = user_input.get("activity_name")

            if activity_to_delete:
                room_data = self.rooms[self.current_room]
                if activity_to_delete in room_data[CONF_ACTIVITIES]:
                    del room_data[CONF_ACTIVITIES][activity_to_delete]
                    _LOGGER.info("Deleted activity %s", activity_to_delete)
                    # Save immediately
                    self._save_config()

            return await self.async_step_activity_menu()

        room_data = self.rooms.get(self.current_room, {})
        activities = room_data.get(CONF_ACTIVITIES, {})

        if not activities:
            return await self.async_step_activity_menu()

        return self.async_show_form(
            step_id="delete_activity",
            data_schema=vol.Schema({
                vol.Required("activity_name"): vol.In(list(activities.keys())),
            }),
            description_placeholders={
                "room": self.current_room or "unknown",
                "warning": "This action cannot be undone!",
            },
        )

    async def async_step_copy_activity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Copy an existing activity."""
        errors = {}

        if user_input is not None:
            source_activity = user_input.get("source_activity")
            new_activity_name = user_input.get("new_activity_name")

            if not new_activity_name or not new_activity_name.strip():
                errors["new_activity_name"] = "invalid_name"
            elif source_activity:
                room_data = self.rooms[self.current_room]
                activities = room_data.get(CONF_ACTIVITIES, {})

                if new_activity_name in activities:
                    errors["new_activity_name"] = "already_exists"
                elif source_activity in activities:
                    # Deep copy the source activity
                    import copy
                    activities[new_activity_name] = copy.deepcopy(activities[source_activity])
                    _LOGGER.info("Copied activity %s to %s", source_activity, new_activity_name)
                    # Save immediately
                    self._save_config()
                    return await self.async_step_activity_menu()
                else:
                    errors["source_activity"] = "not_found"

        room_data = self.rooms.get(self.current_room, {})
        activities = room_data.get(CONF_ACTIVITIES, {})

        if not activities:
            return await self.async_step_activity_menu()

        return self.async_show_form(
            step_id="copy_activity",
            data_schema=vol.Schema({
                vol.Required("source_activity"): vol.In(list(activities.keys())),
                vol.Required("new_activity_name"): str,
            }),
            errors=errors,
            description_placeholders={
                "room": self.current_room or "unknown",
                "info": "Select an activity to copy and enter a name for the new activity.",
            },
        )
