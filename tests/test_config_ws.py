"""Tests for the configuration websocket API used by the panel."""
from __future__ import annotations

import copy
from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.av_scenes.const import DOMAIN

from .common import living_room


async def setup_entry(hass: HomeAssistant, data: dict[str, Any]) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=1, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_get_validate_save(hass: HomeAssistant, devices, hass_ws_client) -> None:
    """Read, check and save; the entry is updated and the room hot-applied."""
    entry = await setup_entry(hass, living_room())
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "av_scenes/config/get"})
    got = (await client.receive_json())["result"]
    assert got["entry_id"] == entry.entry_id
    assert got["rooms"] == living_room()["rooms"]

    rooms = copy.deepcopy(got["rooms"])
    rooms["wz"]["devices"]["beamer"]["delay_after_power"] = 20
    await client.send_json_auto_id({"type": "av_scenes/config/validate", "rooms": rooms})
    assert (await client.receive_json())["result"] == {"error": None, "missing": []}

    await client.send_json_auto_id(
        {"type": "av_scenes/config/save", "rooms": rooms, "revision": got["revision"]}
    )
    saved = (await client.receive_json())["result"]
    await hass.async_block_till_done()
    assert saved["revision"] != got["revision"]
    assert entry.data["rooms"]["wz"]["devices"]["beamer"]["delay_after_power"] == 20
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.rooms["wz"]["devices"]["beamer"]["delay_after_power"] == 20


async def test_validate_reports_path_and_missing(
    hass: HomeAssistant, devices, hass_ws_client
) -> None:
    """Errors name their place; unknown entities are filtered by room."""
    await setup_entry(hass, living_room())
    client = await hass_ws_client(hass)
    rooms = living_room()["rooms"]
    rooms["kino"] = {"devices": {"tv": {"entity_id": "media_player.nope"}}}

    await client.send_json_auto_id(
        {"type": "av_scenes/config/validate", "rooms": rooms, "room": "wz"}
    )
    assert (await client.receive_json())["result"]["missing"] == []

    await client.send_json_auto_id({"type": "av_scenes/config/validate", "rooms": rooms})
    assert (await client.receive_json())["result"]["missing"] == [
        {"room": "kino", "path": "devices.tv.entity_id", "entity_id": "media_player.nope"}
    ]

    rooms["wz"]["activities"]["tv"]["devices"].append("sonos")
    await client.send_json_auto_id({"type": "av_scenes/config/validate", "rooms": rooms})
    error = (await client.receive_json())["result"]["error"]
    assert error["path"] == ["rooms", "wz", "activities", "tv", "devices", "3"]
    assert "unknown device 'sonos'" in error["message"]


async def test_save_refuses_conflicts_and_errors(
    hass: HomeAssistant, devices, hass_ws_client
) -> None:
    """A stale revision or an invalid configuration is not saved."""
    entry = await setup_entry(hass, living_room())
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "av_scenes/config/get"})
    got = (await client.receive_json())["result"]

    # Someone else saves in the meantime
    changed = copy.deepcopy(got["rooms"])
    changed["wz"]["name"] = "Stube"
    hass.config_entries.async_update_entry(entry, data={"rooms": changed})
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {"type": "av_scenes/config/save", "rooms": got["rooms"], "revision": got["revision"]}
    )
    msg = await client.receive_json()
    assert msg["error"]["code"] == "conflict"
    assert entry.data["rooms"]["wz"]["name"] == "Stube"

    await client.send_json_auto_id({"type": "av_scenes/config/get"})
    got = (await client.receive_json())["result"]
    broken = copy.deepcopy(got["rooms"])
    broken["wz"]["devices"]["onkyo"]["delay_after_on"] = "soon"
    await client.send_json_auto_id(
        {"type": "av_scenes/config/save", "rooms": broken, "revision": got["revision"]}
    )
    msg = await client.receive_json()
    assert msg["error"]["code"] == "invalid_config"
    assert "rooms.wz.devices.onkyo.delay_after_on" in msg["error"]["message"]


async def test_config_needs_admin(
    hass: HomeAssistant, devices, hass_ws_client, hass_read_only_access_token
) -> None:
    """Non-admin users cannot read or change the configuration."""
    await setup_entry(hass, living_room())
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id({"type": "av_scenes/config/get"})
    assert (await client.receive_json())["error"]["code"] == "unauthorized"


async def test_get_works_with_broken_config(
    hass: HomeAssistant, devices, hass_ws_client
) -> None:
    """A configuration that fails to load can still be read and fixed."""
    data = living_room()
    data["rooms"]["wz"]["activities"]["tv"]["devices"].append("sonos")
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=1, data=data)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "av_scenes/config/get"})
    got = (await client.receive_json())["result"]
    assert got["rooms"]["wz"]["activities"]["tv"]["devices"][-1] == "sonos"
