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


async def test_stale_entities_and_devices_are_removed(hass: HomeAssistant, devices) -> None:
    """Entities of a deleted activity and the device of a deleted room go away."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    from .common import living_room, setup

    data = living_room()
    data["rooms"]["kino"] = {"name": "Kino", "devices": {}, "activities": {}}
    coordinator = await setup(hass, devices, data)
    entry = coordinator.entry
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    musik = entity_registry.async_get_entity_id("scene", "av_scenes", "av_scenes_wz_musik")
    assert musik is not None
    assert device_registry.async_get_device_by_identifier(("av_scenes", "kino"), entry.entry_id) is not None

    data = living_room()
    del data["rooms"]["wz"]["activities"]["musik"]
    hass.config_entries.async_update_entry(entry, data=data)
    await hass.async_block_till_done()

    assert entity_registry.async_get(musik) is None
    assert entity_registry.async_get_entity_id("scene", "av_scenes", "av_scenes_wz_tv")
    assert device_registry.async_get_device_by_identifier(("av_scenes", "kino"), entry.entry_id) is None
    assert device_registry.async_get_device_by_identifier(("av_scenes", "wz"), entry.entry_id) is not None


async def test_scene_names_follow_the_device(hass: HomeAssistant, devices) -> None:
    """Scenes are named like the other entities: device name plus activity."""
    from .common import setup, living_room

    await setup(hass, devices, living_room())
    state = hass.states.get("scene.av_wohnzimmer_tv")
    assert state is not None
    assert state.attributes["friendly_name"] == "AV: Wohnzimmer TV"
