"""Tests for the config and options flow."""
from __future__ import annotations

import copy
from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import area_registry as ar, entity_registry as er

from custom_components.av_scenes.const import DOMAIN

ROOM = {
    "name": "Wohnzimmer",
    "devices": {"onkyo": {"entity_id": "media_player.onkyo_receiver"}},
    "activities": {"tv": {"name": "TV", "devices": ["onkyo"]}},
}


async def setup_entry(hass: HomeAssistant, rooms: dict[str, Any] | None = None) -> MockConfigEntry:
    hass.states.async_set("media_player.onkyo_receiver", "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        data={"rooms": copy.deepcopy(rooms if rooms is not None else {"wz": ROOM})},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def open_room_editor(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, Any]:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "select_room"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"room": "wz"}
    )
    assert result["step_id"] == "edit_room"
    return result


async def test_user_flow(hass: HomeAssistant) -> None:
    """Setup creates an empty v2 entry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"rooms": {}}
    assert result["result"].version == 2


async def test_only_one_entry(hass: HomeAssistant) -> None:
    """All rooms live in one entry; a second setup is refused."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    await hass.config_entries.flow.async_configure(result["flow_id"], {})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_edit_room_applies_without_reload(hass: HomeAssistant) -> None:
    """Changing a room's content keeps the entities and the running state."""
    entry = await setup_entry(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.runtime("wz").activity = "tv"
    coordinator.runtime("wz").state = "active"

    result = await open_room_editor(hass, entry)
    room = copy.deepcopy(ROOM)
    room["devices"]["onkyo"]["delay_after_off"] = 5
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"config": room}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["rooms"]["wz"] == room
    assert hass.data[DOMAIN][entry.entry_id] is coordinator
    assert coordinator.rooms["wz"]["devices"]["onkyo"]["delay_after_off"] == 5
    assert coordinator.activity_states["wz"] == "active"


async def test_new_activity_reloads(hass: HomeAssistant) -> None:
    """A new activity needs new entities, so the entry is reloaded."""
    entry = await setup_entry(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    result = await open_room_editor(hass, entry)
    room = copy.deepcopy(ROOM)
    room["activities"]["musik"] = {"name": "Musik", "devices": ["onkyo"]}
    await hass.config_entries.options.async_configure(result["flow_id"], {"config": room})
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][entry.entry_id] is not coordinator
    # The generated entity_id may carry an area prefix, so look it up
    entity_id = er.async_get(hass).async_get_entity_id("scene", DOMAIN, "av_scenes_wz_musik")
    assert entity_id is not None
    assert hass.states.get(entity_id) is not None


async def test_invalid_yaml_shows_path(hass: HomeAssistant) -> None:
    """Validation errors name the place in the configuration."""
    entry = await setup_entry(hass)
    result = await open_room_editor(hass, entry)
    room = copy.deepcopy(ROOM)
    room["activities"]["tv"]["devices"] = ["vu"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"config": room}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_config"}
    assert "rooms.wz.activities.tv.devices.0" in result["description_placeholders"]["error"]
    assert entry.data["rooms"]["wz"] == ROOM


async def test_missing_entity_needs_confirmation(hass: HomeAssistant) -> None:
    """Unknown entities are warnings: back to the editor or save anyway."""
    entry = await setup_entry(hass)
    result = await open_room_editor(hass, entry)
    room = copy.deepcopy(ROOM)
    room["devices"]["beamer"] = {"entity_id": "media_player.epson_beamer"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"config": room}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "confirm_missing"
    assert "media_player.epson_beamer" in result["description_placeholders"]["entities"]

    # Back keeps the unsaved text
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "back_to_room"}
    )
    assert result["step_id"] == "edit_room"
    assert entry.data["rooms"]["wz"] == ROOM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"config": room}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "save_anyway"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["rooms"]["wz"] == room


async def test_add_room_from_area(hass: HomeAssistant) -> None:
    """A room created from an area takes its name."""
    area = ar.async_get(hass).async_create("Kino")
    entry = await setup_entry(hass, {})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert [*result["menu_options"]] == ["add_room", "edit_all"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_room"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"area_id": area.id}
    )
    assert result["step_id"] == "edit_room"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"config": {"name": "Kino", "area_id": area.id, "devices": {}, "activities": {}}},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["rooms"] == {
        "kino": {"name": "Kino", "area_id": area.id, "devices": {}, "activities": {}}
    }


async def test_delete_room(hass: HomeAssistant) -> None:
    """Deleting a room removes it from the entry."""
    entry = await setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "delete_room"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"room": "wz"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["rooms"] == {}


async def test_edit_all(hass: HomeAssistant) -> None:
    """The whole configuration can be replaced at once."""
    entry = await setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "edit_all"}
    )
    rooms = {"wz": ROOM, "kino": {"name": "Kino"}}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"config": rooms}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["rooms"] == rooms


async def test_room_editor_ignores_other_rooms(hass: HomeAssistant) -> None:
    """A wrong entity in another room does not show up when saving this one."""
    other = {"name": "Kino", "devices": {"beamer": {"entity_id": "media_player.epson_beamer"}}}
    entry = await setup_entry(hass, {"wz": ROOM, "kino": other})
    result = await open_room_editor(hass, entry)
    room = copy.deepcopy(ROOM)
    room["devices"]["onkyo"]["delay_after_off"] = 5

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"config": room}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["rooms"]["wz"] == room
