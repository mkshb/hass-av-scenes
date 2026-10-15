"""Tests for the remote control: command routing, service and websocket."""
from __future__ import annotations

from typing import Any

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .common import BEAMER, ONKYO, VU, Devices, living_room, setup
from custom_components.av_scenes.const import DOMAIN
from custom_components.av_scenes.control import routing
from custom_components.av_scenes.model import validate_config


@pytest.fixture
def player_calls(hass: HomeAssistant) -> list[tuple[str, dict[str, Any]]]:
    """Record media_player and test actions; the integrations are not loaded."""
    calls: list[tuple[str, dict[str, Any]]] = []

    async def record(call: ServiceCall) -> None:
        calls.append((f"{call.domain}.{call.service}", dict(call.data)))

    for service in (
        "volume_up", "volume_down", "volume_mute", "volume_set", "media_next_track",
        "media_previous_track", "media_play_pause",
    ):
        hass.services.async_register("media_player", service, record)
    hass.services.async_register("test", "key", record)
    return calls


def remote_room() -> dict[str, Any]:
    """Living room with a navigable VU+ and a few remote buttons."""
    data = living_room()
    room = data["rooms"]["wz"]
    room["devices"]["vu"]["commands"] = {
        "ok": [{"action": "test.key", "data": {"code": "KEY_OK", "entity": "{{ entity_id }}"}}],
        "1": {"action": "test.key", "data": {"code": "KEY_1"}},
    }
    room["activities"]["tv"]["remote"] = {"buttons": ["guide", {"command": "netflix",
                                                               "name": "Netflix"}]}
    room["activities"]["tv"]["commands"] = {
        "netflix": [{"action": "test.key", "data": {"code": "{{ command }}"}}]
    }
    return data


async def send(hass: HomeAssistant, command: str, **data: Any) -> None:
    await hass.services.async_call(
        DOMAIN, "send_command", {"room": "wz", "command": command, **data}, blocking=True
    )


def test_default_routing() -> None:
    """Volume to the first media player, channels to a separate source, navigation by commands."""
    room = validate_config(remote_room())["rooms"]["wz"]
    assert routing(room, room["activities"]["tv"]) == {
        "volume": "onkyo",
        "channels": "vu",
        "transport": "vu",
        "navigation": "vu",
    }
    # The receiver alone: no channel keys that only repeat next/previous
    assert routing(room, room["activities"]["musik"]) == {
        "volume": "onkyo",
        "channels": None,
        "transport": "onkyo",
        "navigation": None,
    }


def test_explicit_routing() -> None:
    """Explicit routing wins; null hides a group."""
    data = remote_room()
    data["rooms"]["wz"]["activities"]["tv"]["remote"].update(volume="beamer", transport=None)
    room = validate_config(data)["rooms"]["wz"]
    route = routing(room, room["activities"]["tv"])
    assert route["volume"] == "beamer"
    assert route["transport"] is None


def test_routing_to_unknown_device_is_invalid() -> None:
    data = remote_room()
    data["rooms"]["wz"]["activities"]["tv"]["remote"]["volume"] = "sonos"
    with pytest.raises(vol.Invalid) as err:
        validate_config(data)
    assert err.value.path == ["rooms", "wz", "activities", "tv", "remote", "volume"]


async def test_send_command_routes_to_activity_devices(
    hass: HomeAssistant, devices: Devices, player_calls
) -> None:
    """While TV runs, volume goes to the Onkyo and channels to the VU+."""
    coordinator = await setup(hass, devices, remote_room())
    await coordinator.async_start_activity("wz", "tv")
    hass.states.async_set(ONKYO, "on", {"is_volume_muted": False})

    await send(hass, "volume_up")
    await send(hass, "mute")
    await send(hass, "volume_set", value=0.4)
    await send(hass, "channel_up")

    assert player_calls == [
        ("media_player.volume_up", {"entity_id": ONKYO}),
        ("media_player.volume_mute", {"entity_id": ONKYO, "is_volume_muted": True}),
        ("media_player.volume_set", {"entity_id": ONKYO, "volume_level": 0.4}),
        ("media_player.media_next_track", {"entity_id": VU}),
    ]


async def test_send_command_runs_configured_actions(
    hass: HomeAssistant, devices: Devices, player_calls
) -> None:
    """Device and activity commands run their HA actions with variables."""
    coordinator = await setup(hass, devices, remote_room())
    await coordinator.async_start_activity("wz", "tv")

    await send(hass, "ok")  # navigation group -> vu
    await send(hass, "1")  # not a standard command -> first device that knows it
    await send(hass, "netflix")  # the activity's own command

    assert player_calls == [
        ("test.key", {"code": "KEY_OK", "entity": VU}),
        ("test.key", {"code": "KEY_1"}),
        ("test.key", {"code": "netflix"}),
    ]


async def test_send_command_errors(hass: HomeAssistant, devices: Devices, player_calls) -> None:
    """Commands that cannot be routed raise instead of silently doing nothing."""
    await setup(hass, devices, remote_room())

    with pytest.raises(ServiceValidationError) as err:
        await send(hass, "volume_up")
    assert err.value.translation_key == "no_activity"

    # A device addressed directly works while nothing runs
    await send(hass, "volume_down", device="beamer")
    assert player_calls == [("media_player.volume_down", {"entity_id": BEAMER})]

    with pytest.raises(ServiceValidationError) as err:
        await send(hass, "ok", device="onkyo")
    assert err.value.translation_key == "unknown_command"

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "send_command", {"room": "kino", "command": "ok"}, blocking=True
        )
    assert err.value.translation_key == "unknown_room"


async def test_websocket_rooms_and_subscribe(
    hass: HomeAssistant, devices: Devices, player_calls, hass_ws_client
) -> None:
    """The card gets the room view now, on every change and across reloads."""
    coordinator = await setup(hass, devices, remote_room())
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "av_scenes/control/rooms"})
    msg = await client.receive_json()
    assert msg["result"] == [
        {"entry_id": coordinator.entry.entry_id, "room": "wz", "name": "Wohnzimmer",
         "area_id": None}
    ]

    await client.send_json_auto_id({"type": "av_scenes/control/subscribe", "room": "wz"})
    assert (await client.receive_json())["success"]
    view = (await client.receive_json())["event"]
    assert view["state"] == "idle"
    assert view["remote"] is None
    assert [a["name"] for a in view["activities"]] == ["TV", "Musik"]

    await coordinator.async_start_activity("wz", "tv")
    while (view := (await client.receive_json())["event"])["state"] != "active":
        pass
    assert view["activity"] == "tv"
    groups = view["remote"]["groups"]
    assert groups["volume"] == {
        "device": "onkyo",
        "entity_id": ONKYO,
        "commands": ["volume_up", "volume_down", "mute", "volume_set"],
    }
    assert groups["navigation"]["commands"] == ["ok"]
    assert view["remote"]["buttons"][1] == {
        "command": "netflix", "name": "Netflix", "icon": None, "device": None
    }

    # A reload replaces the coordinator; the subscription follows the room
    await hass.config_entries.async_reload(coordinator.entry.entry_id)
    await hass.async_block_till_done()
    events = []
    while True:
        events.append((await client.receive_json())["event"])
        if events[-1] is not None and events[-1]["state"] == "active":
            break
    assert None in events  # while unloaded

    # Unloading for good sends null
    await hass.config_entries.async_unload(coordinator.entry.entry_id)
    assert (await client.receive_json())["event"] is None
