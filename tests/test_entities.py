"""Tests for the entity platforms."""
from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.av_scenes.const import DOMAIN

DATA = {
    "rooms": {
        "wz": {
            "name": "Wohnzimmer",
            "devices": {"onkyo": {"entity_id": "media_player.onkyo_receiver"}},
            "activities": {
                "tv": {"name": "TV", "devices": ["onkyo"]},
                "musik": {"name": "Musik", "devices": ["onkyo"]},
            },
        }
    }
}


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_translated_names_and_states(hass: HomeAssistant) -> None:
    """Names come from the translations; states are stable keys."""
    hass.states.async_set("media_player.onkyo_receiver", "off")
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=1, data=DATA)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sensor = hass.states.get(_entity_id(hass, "sensor", "av_scenes_activity_state_wz"))
    select = hass.states.get(_entity_id(hass, "select", "av_scenes_select_wz"))
    switch = hass.states.get(_entity_id(hass, "switch", "av_scenes_activity_wz"))

    assert sensor.attributes["friendly_name"] == "AV: Wohnzimmer Activity"
    assert select.attributes["friendly_name"] == "AV: Wohnzimmer Scene"
    assert switch.attributes["friendly_name"] == "AV: Wohnzimmer Active"

    assert sensor.state == "idle"
    assert select.state == "idle"
    assert select.attributes["options"] == ["idle", "Musik", "TV"]  # by name without `order`
    assert switch.state == "off"


async def test_select_starts_by_display_name(hass: HomeAssistant) -> None:
    """Selecting an activity name starts it; the state shows that name."""
    hass.states.async_set("media_player.onkyo_receiver", "on")
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=1, data=DATA)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    select_id = _entity_id(hass, "select", "av_scenes_select_wz")

    await hass.services.async_call(
        "select", "select_option", {"entity_id": select_id, "option": "Musik"}, blocking=True
    )

    assert hass.states.get(select_id).state == "Musik"
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.active_activities["wz"] == "musik"
