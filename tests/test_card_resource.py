"""Tests for the card's dashboard resource."""
from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.av_scenes.card_resource import (
    async_register_card_resource,
    async_remove_card_resource,
)
from custom_components.av_scenes.const import DOMAIN

from .common import living_room

BASE = "/av_scenes_static/av-scenes-card.js"


def urls(hass: HomeAssistant) -> list[str]:
    return [item["url"] for item in hass.data["lovelace"].resources.async_items()]


async def test_register_update_and_remove(hass: HomeAssistant) -> None:
    """The resource is added once, follows the version and can be removed."""
    assert await async_setup_component(hass, "lovelace", {})
    resources = hass.data["lovelace"].resources
    await resources.async_create_item({"res_type": "module", "url": "/local/other.js"})

    assert await async_register_card_resource(hass, BASE, f"{BASE}?v=1")
    assert await async_register_card_resource(hass, BASE, f"{BASE}?v=1")
    assert urls(hass) == ["/local/other.js", f"{BASE}?v=1"]

    # A new version updates the entry; a duplicate is cleaned up
    await resources.async_create_item({"res_type": "module", "url": BASE})
    assert await async_register_card_resource(hass, BASE, f"{BASE}?v=2")
    assert urls(hass) == ["/local/other.js", f"{BASE}?v=2"]

    await async_remove_card_resource(hass, BASE)
    assert urls(hass) == ["/local/other.js"]


async def test_yaml_resources_are_left_alone(hass: HomeAssistant) -> None:
    """With resources in YAML the caller has to load the card itself."""
    assert await async_setup_component(
        hass, "lovelace", {"lovelace": {"resource_mode": "yaml", "resources": []}}
    )
    assert not await async_register_card_resource(hass, BASE, f"{BASE}?v=1")


async def test_removing_the_last_entry_removes_the_resource(
    hass: HomeAssistant, devices
) -> None:
    """The resource goes with the last entry, not before."""
    assert await async_setup_component(hass, "lovelace", {})
    assert await async_register_card_resource(hass, BASE, f"{BASE}?v=1")
    entries = []
    for _ in range(2):
        entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=1, data=living_room())
        entry.add_to_hass(hass)
        entries.append(entry)
    assert await hass.config_entries.async_setup(entries[0].entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_remove(entries[0].entry_id)
    assert urls(hass) == [f"{BASE}?v=1"]
    await hass.config_entries.async_remove(entries[1].entry_id)
    assert urls(hass) == []
