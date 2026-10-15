"""Config flow for AV Scenes.

Rooms are edited as YAML (one editor per room, or the whole configuration at
once). Every save is validated against the v2 schema; entities that do not
exist yet are shown as warnings before saving, since a device without power
can legitimately be missing.
"""
from __future__ import annotations

import copy
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar, selector
from homeassistant.util import slugify

from .const import (
    CONF_ACTIVITIES,
    CONF_AREA_ID,
    CONF_DEVICES,
    CONF_NAME,
    CONF_ROOMS,
    CONFIG_MINOR_VERSION,
    CONFIG_VERSION,
    DOMAIN,
)
from .model import async_validate_config, find_missing_entities

CONF_ROOM = "room"
CONF_CONFIG = "config"


class AVScenesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create an AV Scenes entry."""

    VERSION = CONFIG_VERSION
    MINOR_VERSION = CONFIG_MINOR_VERSION

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create an empty entry; rooms are added in the options."""
        if user_input is not None:
            return self.async_create_entry(title="AV Scenes", data={CONF_ROOMS: {}})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AVScenesOptionsFlow:
        """Return the options flow."""
        return AVScenesOptionsFlow()


class AVScenesOptionsFlow(OptionsFlow):
    """Edit rooms as YAML."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._rooms: dict[str, Any] | None = None
        self._room_id: str | None = None
        self._pending: dict[str, Any] | None = None
        self._return_step: str = "edit_room"

    @property
    def rooms(self) -> dict[str, Any]:
        """Working copy of the rooms."""
        if self._rooms is None:
            self._rooms = copy.deepcopy(dict(self.config_entry.data.get(CONF_ROOMS) or {}))
        return self._rooms

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Main menu."""
        options = ["add_room"]
        if self.rooms:
            options = ["select_room", "add_room", "delete_room"]
        options.append("edit_all")
        return self.async_show_menu(step_id="init", menu_options=options)

    def _room_selector(self) -> selector.SelectSelector:
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=room_id, label=room.get(CONF_NAME, room_id))
                    for room_id, room in self.rooms.items()
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )

    async def async_step_select_room(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the room to edit."""
        if user_input is not None:
            self._room_id = user_input[CONF_ROOM]
            return await self.async_step_edit_room()
        return self.async_show_form(
            step_id="select_room",
            data_schema=vol.Schema({vol.Required(CONF_ROOM): self._room_selector()}),
        )

    async def async_step_add_room(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create an empty room, then open its editor."""
        errors: dict[str, str] = {}
        if user_input is not None:
            area_id = user_input.get(CONF_AREA_ID)
            name = (user_input.get(CONF_NAME) or "").strip()
            if not name and area_id and (area := ar.async_get(self.hass).async_get_area(area_id)):
                name = area.name
            room_id = slugify(name) if name else ""
            if not room_id:
                errors["base"] = "name_required"
            elif room_id in self.rooms:
                errors["base"] = "room_exists"
            else:
                room: dict[str, Any] = {CONF_NAME: name, CONF_DEVICES: {}, CONF_ACTIVITIES: {}}
                if area_id:
                    room[CONF_AREA_ID] = area_id
                self.rooms[room_id] = room
                self._room_id = room_id
                return await self.async_step_edit_room()

        return self.async_show_form(
            step_id="add_room",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_AREA_ID): selector.AreaSelector(),
                    vol.Optional(CONF_NAME): selector.TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_delete_room(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Delete a room."""
        if user_input is not None:
            rooms = copy.deepcopy(self.rooms)
            rooms.pop(user_input[CONF_ROOM], None)
            return self._save(rooms)
        return self.async_show_form(
            step_id="delete_room",
            data_schema=vol.Schema({vol.Required(CONF_ROOM): self._room_selector()}),
        )

    # ------------------------------------------------------------------
    # Editors
    # ------------------------------------------------------------------

    async def async_step_edit_room(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit one room as YAML."""
        assert self._room_id is not None
        room_id = self._room_id
        errors: dict[str, str] = {}
        placeholders = {"room": self.rooms[room_id].get(CONF_NAME, room_id), "error": ""}
        current: dict[str, Any] = self.rooms[room_id]

        if user_input is not None:
            current = user_input.get(CONF_CONFIG) or {}
            rooms = copy.deepcopy(self.rooms)
            rooms[room_id] = current
            self._return_step = "edit_room"
            result = await self._async_validate_and_save(rooms, errors, placeholders)
            if result is not None:
                return result

        return self.async_show_form(
            step_id="edit_room",
            data_schema=vol.Schema(
                {vol.Required(CONF_CONFIG, default=current): selector.ObjectSelector()}
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_edit_all(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit all rooms at once as YAML."""
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        current: dict[str, Any] = self.rooms

        if user_input is not None:
            current = user_input.get(CONF_CONFIG) or {}
            self._return_step = "edit_all"
            if not isinstance(current, dict):
                errors["base"] = "invalid_config"
                placeholders["error"] = "top level must be a mapping of rooms"
            else:
                result = await self._async_validate_and_save(current, errors, placeholders)
                if result is not None:
                    return result

        return self.async_show_form(
            step_id="edit_all",
            data_schema=vol.Schema(
                {vol.Required(CONF_CONFIG, default=current): selector.ObjectSelector()}
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def _async_validate_and_save(
        self,
        rooms: dict[str, Any],
        errors: dict[str, str],
        placeholders: dict[str, str],
    ) -> ConfigFlowResult | None:
        """Validate; save, ask about warnings, or fill in the errors."""
        data = {**self.config_entry.data, CONF_ROOMS: rooms}
        try:
            await async_validate_config(self.hass, data)
        except vol.Invalid as err:
            path = ".".join(str(p) for p in err.path)
            errors["base"] = "invalid_config"
            placeholders["error"] = f"{path}: {err.msg}" if path else str(err.msg)
            return None

        missing = find_missing_entities(self.hass, data)
        if missing:
            self._pending = rooms
            return await self.async_step_confirm_missing()
        return self._save(rooms)

    async def async_step_confirm_missing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show unknown entities before saving."""
        assert self._pending is not None
        missing = find_missing_entities(
            self.hass, {**self.config_entry.data, CONF_ROOMS: self._pending}
        )
        lines = "\n".join(
            f"- `{ref.entity_id}` ({ref.room_id}: {ref.path})" for ref in missing
        )
        return self.async_show_menu(
            step_id="confirm_missing",
            menu_options=["save_anyway", self._return_step_back()],
            description_placeholders={"entities": lines},
        )

    def _return_step_back(self) -> str:
        return "back_to_room" if self._return_step == "edit_room" else "back_to_all"

    async def async_step_save_anyway(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Save despite unknown entities."""
        assert self._pending is not None
        return self._save(self._pending)

    async def async_step_back_to_room(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Return to the room editor with the unsaved text."""
        assert self._pending is not None and self._room_id is not None
        self.rooms[self._room_id] = self._pending[self._room_id]
        return await self.async_step_edit_room()

    async def async_step_back_to_all(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Return to the full editor with the unsaved text."""
        assert self._pending is not None
        self._rooms = self._pending
        return await self.async_step_edit_all()

    @callback
    def _save(self, rooms: dict[str, Any]) -> ConfigFlowResult:
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, CONF_ROOMS: rooms}
        )
        return self.async_create_entry(data={})
