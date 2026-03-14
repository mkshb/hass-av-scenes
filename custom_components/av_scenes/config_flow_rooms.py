"""Rooms management mixin for AV Scenes config flow."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import area_registry as ar

from .const import (
    CONF_ROOMS,
    CONF_ACTIVITIES,
)

_LOGGER = logging.getLogger(__name__)


class RoomsFlowMixin:
    """Mixin for room management flow steps."""

    async def async_step_room_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show room management menu."""
        _LOGGER.debug("Options flow: room_menu called with input: %s", user_input)
        _LOGGER.debug("Current rooms: %s", list(self.rooms.keys()))

        if user_input is not None:
            action = user_input.get("action")

            if action == "add_room":
                return await self.async_step_add_room()
            elif action == "edit_room":
                return await self.async_step_select_room()
            elif action == "delete_room":
                return await self.async_step_delete_room()
            elif action == "finish":
                # Update the config entry with new data
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={CONF_ROOMS: self.rooms}
                )
                return self.async_create_entry(title="", data={})

        room_list = "\n".join([f"- {room_id}" for room_id in self.rooms.keys()])
        if not room_list:
            room_list = "No rooms configured yet"

        actions = {
            "add_room": "Add new room",
        }

        # Only show edit/delete if there are rooms
        if self.rooms:
            actions["edit_room"] = "Edit existing room"
            actions["delete_room"] = "Delete room"

        # Finish always at the bottom
        actions["finish"] = "Finish and save"

        return self.async_show_form(
            step_id="room_menu",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(actions),
            }),
            description_placeholders={
                "rooms": room_list,
            },
        )

    async def async_step_add_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new room."""
        _LOGGER.debug("Options flow: add_room called with input: %s", user_input)
        errors = {}

        if user_input is not None:
            try:
                room_id = user_input.get("room_id")

                # If custom room selected, show custom name input
                if room_id == "custom":
                    return await self.async_step_add_custom_room()

                # Check if room already exists
                if room_id in self.rooms:
                    errors["room_id"] = "already_exists"
                    _LOGGER.warning("Room %s already exists", room_id)
                else:
                    # Get room name - use custom name if provided, otherwise use area name
                    room_name = user_input.get("room_name")

                    if not room_name or not room_name.strip():
                        # Get area name from registry
                        area_registry = ar.async_get(self.hass)
                        area = area_registry.async_get_area(room_id)
                        room_name = area.name if area else room_id

                    _LOGGER.debug("Attempting to add room: id=%s, name=%s", room_id, room_name)

                    self.current_room = room_id
                    self.rooms[room_id] = {
                        "name": room_name,
                        CONF_ACTIVITIES: {},
                    }
                    _LOGGER.info("Created room %s (%s)", room_id, room_name)
                    return await self.async_step_activity_menu()
            except Exception as ex:
                _LOGGER.exception("Error in add_room: %s", ex)
                errors["base"] = "unknown"

        # Get all areas from Home Assistant
        area_registry = ar.async_get(self.hass)
        areas = []

        for area in area_registry.async_list_areas():
            # Use id as key and name as display
            areas.append((area.id, area.name))

        # Sort by name
        areas.sort(key=lambda x: x[1])

        # Create area options
        area_options = {"custom": "-- Create custom room --"}
        for area_id, area_name in areas:
            area_options[area_id] = area_name

        if not areas:
            area_options["custom"] = "-- Enter custom room name --"

        return self.async_show_form(
            step_id="add_room",
            data_schema=vol.Schema({
                vol.Required("room_id"): vol.In(area_options),
                vol.Optional("room_name"): str,
            }),
            errors=errors,
            description_placeholders={
                "info": "Select an existing Home Assistant area or create a custom room. "
                "You can optionally provide a custom display name."
            },
        )

    async def async_step_add_custom_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a custom room with manual ID and name."""
        errors = {}

        if user_input is not None:
            try:
                room_id = user_input.get("custom_room_id")
                room_name = user_input.get("custom_room_name", room_id)

                if not room_id or not room_id.strip():
                    errors["custom_room_id"] = "invalid_name"
                elif room_id in self.rooms:
                    errors["custom_room_id"] = "already_exists"
                else:
                    self.current_room = room_id
                    self.rooms[room_id] = {
                        "name": room_name,
                        CONF_ACTIVITIES: {},
                    }
                    _LOGGER.info("Created custom room %s (%s)", room_id, room_name)
                    return await self.async_step_activity_menu()
            except Exception as ex:
                _LOGGER.exception("Error in add_custom_room: %s", ex)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="add_custom_room",
            data_schema=vol.Schema({
                vol.Required("custom_room_id"): str,
                vol.Required("custom_room_name"): str,
            }),
            errors=errors,
            description_placeholders={
                "info": "Enter a unique room ID (lowercase, no spaces) and a display name."
            },
        )

    async def async_step_select_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a room to edit."""
        if user_input is not None:
            self.current_room = user_input.get("room_id")
            return await self.async_step_activity_menu()

        if not self.rooms:
            return await self.async_step_room_menu()

        return self.async_show_form(
            step_id="select_room",
            data_schema=vol.Schema({
                vol.Required("room_id"): vol.In(list(self.rooms.keys())),
            }),
        )

    async def async_step_delete_room(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Delete a room."""
        if user_input is not None:
            room_to_delete = user_input.get("room_id")

            if room_to_delete in self.rooms:
                room_name = self.rooms[room_to_delete].get("name", room_to_delete)
                del self.rooms[room_to_delete]
                _LOGGER.info("Deleted room %s (%s)", room_to_delete, room_name)
                # Save immediately
                self._save_config()

            return await self.async_step_room_menu()

        if not self.rooms:
            return await self.async_step_room_menu()

        return self.async_show_form(
            step_id="delete_room",
            data_schema=vol.Schema({
                vol.Required("room_id"): vol.In(list(self.rooms.keys())),
            }),
            description_placeholders={
                "warning": "This will delete the room and all its activities. This action cannot be undone!",
            },
        )
