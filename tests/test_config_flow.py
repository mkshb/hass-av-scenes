"""Tests for the AV Scenes config and options flow."""
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.av_scenes.const import DOMAIN, CONF_ROOMS


async def test_user_flow_creates_entry(hass: HomeAssistant):
    """The user step creates an entry with an empty rooms container."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ROOMS: {}}


async def test_options_flow_add_custom_room(hass: HomeAssistant):
    """Adding a custom room through the options flow persists it."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ROOMS: {}})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "room_menu"

    # Choose "add_room"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "add_room"}
    )
    assert result["step_id"] == "add_room"

    # Pick the custom-room sentinel -> custom room form
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"room_id": "custom"}
    )
    assert result["step_id"] == "add_custom_room"

    # Enter a custom room -> lands in the activity menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"custom_room_id": "cinema", "custom_room_name": "Cinema"},
    )
    assert result["step_id"] == "activity_menu"

    # Back to the room menu, then finish to persist the configuration
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "back"}
    )
    assert result["step_id"] == "room_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "finish"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    assert "cinema" in entry.data[CONF_ROOMS]
    assert entry.data[CONF_ROOMS]["cinema"]["name"] == "Cinema"
