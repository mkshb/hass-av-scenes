"""Activities management mixin for AV Scenes config flow."""
from __future__ import annotations

import copy
import logging
from typing import Any

import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ACTIVITIES,
    CONF_ACTIVITY_NAME,
    CONF_STEPS,
)
from .config_flow_helpers import describe_step, translatable_select, value_select

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

        options = ["add_activity"]
        if activities:
            options += ["edit_activity", "delete_activity", "copy_activity"]
        options.append("back")

        return self.async_show_form(
            step_id="activity_menu",
            data_schema=vol.Schema({
                vol.Required("action"): translatable_select(options, "activity_action"),
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
                vol.Required("activity_name"): value_select(list(activities.keys())),
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

        step_list = [
            f"{idx}. {describe_step(self.hass, step)}"
            for idx, step in enumerate(steps, 1)
        ]
        step_list_str = "\n".join(step_list) if step_list else "No steps configured"

        return self.async_show_form(
            step_id="edit_activity",
            data_schema=vol.Schema({
                vol.Required("action"): translatable_select(
                    ["edit_steps", "rename", "back"], "edit_activity_action"
                ),
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
                vol.Required("activity_name"): value_select(list(activities.keys())),
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
                vol.Required("source_activity"): value_select(list(activities.keys())),
                vol.Required("new_activity_name"): str,
            }),
            errors=errors,
            description_placeholders={
                "room": self.current_room or "unknown",
                "info": "Select an activity to copy and enter a name for the new activity.",
            },
        )
