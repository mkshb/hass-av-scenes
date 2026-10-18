"""Tests for the remote control: command routing, service and websocket."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .common import BEAMER, ONKYO, VU, Devices, living_room, setup
from custom_components.av_scenes.const import DOMAIN
from custom_components.av_scenes.control import (
    media_entity,
    remote_view,
    routing,
    settings_view,
)
from custom_components.av_scenes.model import validate_config


@pytest.fixture
def player_calls(hass: HomeAssistant) -> list[tuple[str, dict[str, Any]]]:
    """Record media_player and test actions; the integrations are not loaded."""
    calls: list[tuple[str, dict[str, Any]]] = []

    async def record(call: ServiceCall) -> None:
        calls.append((f"{call.domain}.{call.service}", dict(call.data)))

    for service in (
        "volume_up", "volume_down", "volume_mute", "volume_set", "media_next_track",
        "media_previous_track", "media_play_pause", "media_play", "media_pause", "media_stop",
        "select_source", "select_sound_mode",
    ):
        hass.services.async_register("media_player", service, record)
    hass.services.async_register("test", "key", record)
    hass.services.async_register("remote", "send_command", record)
    return calls


def remote_room() -> dict[str, Any]:
    """Living room with a navigable VU+ and a few remote buttons."""
    data = living_room()
    room = data["rooms"]["wz"]
    room["devices"]["vu"]["commands"] = {
        "ok": [{"action": "test.key", "data": {"code": "KEY_OK", "entity": "{{ entity_id }}"}}],
        "1": {"action": "test.key", "data": {"code": "KEY_1"}},
    }
    room["activities"]["tv"]["order"] = 1
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


def test_media_entity() -> None:
    """Title and artwork come from the device playback goes to, else the last player."""
    data = remote_room()
    room_cfg = data["rooms"]["wz"]
    room_cfg["devices"]["light"] = {"entity_id": "light.wz"}
    room_cfg["activities"]["licht"] = {"devices": ["light"]}
    room = validate_config(data)["rooms"]["wz"]
    assert media_entity(room, room["activities"]["tv"]) == VU
    assert media_entity(room, room["activities"]["musik"]) == ONKYO
    assert media_entity(room, room["activities"]["licht"]) is None

    # Playback routed to the receiver, but the receiver is the one playing
    room_cfg["activities"]["tv"]["remote"]["transport"] = "onkyo"
    room = validate_config(data)["rooms"]["wz"]
    assert media_entity(room, room["activities"]["tv"]) == ONKYO

    # Playback hidden: still the source behind the receiver
    room_cfg["activities"]["tv"]["remote"]["transport"] = None
    room = validate_config(data)["rooms"]["wz"]
    assert media_entity(room, room["activities"]["tv"]) == VU
    assert remote_view(room, room["activities"]["tv"])["media"] == VU


def test_touchpad() -> None:
    """A swipe area for navigation to a remote entity, unless the activity says otherwise."""
    data = remote_room()
    room_cfg = data["rooms"]["wz"]
    room_cfg["devices"]["atv"] = {"entity_id": "media_player.atv", "remote_entity": "remote.atv"}
    room_cfg["activities"]["atv"] = {"devices": ["onkyo", "atv"]}
    room = validate_config(data)["rooms"]["wz"]
    # The VU+ navigates with own commands: arrow keys
    assert remote_view(room, room["activities"]["tv"])["groups"]["navigation"]["touchpad"] is False
    assert remote_view(room, room["activities"]["atv"])["groups"]["navigation"]["touchpad"] is True

    room_cfg["activities"]["atv"]["remote"] = {"touchpad": False}
    room_cfg["activities"]["tv"]["remote"]["touchpad"] = True
    room = validate_config(data)["rooms"]["wz"]
    assert remote_view(room, room["activities"]["atv"])["groups"]["navigation"]["touchpad"] is False
    assert remote_view(room, room["activities"]["tv"])["groups"]["navigation"]["touchpad"] is True

    # Without navigation there is nothing to swipe
    assert "navigation" not in remote_view(room, room["activities"]["musik"])["groups"]


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
    await send(hass, "volume_set", value="0.25")  # text from the action editor
    await send(hass, "channel_up")

    assert player_calls == [
        ("media_player.volume_up", {"entity_id": ONKYO}),
        ("media_player.volume_mute", {"entity_id": ONKYO, "is_volume_muted": True}),
        ("media_player.volume_set", {"entity_id": ONKYO, "volume_level": 0.4}),
        ("media_player.volume_set", {"entity_id": ONKYO, "volume_level": 0.25}),
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
        "command": "netflix", "value": None, "name": "Netflix", "icon": None, "device": None
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


async def test_send_command_reconnects_first(
    hass: HomeAssistant, devices: Devices, player_calls
) -> None:
    """A lost connection is brought back (one reload) before the command goes out."""
    from unittest.mock import patch

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from homeassistant.helpers import entity_registry as er

    apple = MockConfigEntry(domain="apple_tv")
    apple.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "remote", "apple_tv", "x", suggested_object_id="vu", config_entry=apple
    )
    data = remote_room()
    data["rooms"]["wz"]["devices"]["vu"]["ready"] = {
        "entity_id": "remote.vu", "state": "on", "timeout": 5,
        "reload_integration": True, "on_timeout": "abort",
    }
    hass.states.async_set("remote.vu", "on")
    coordinator = await setup(hass, devices, data)
    reloads: list[str] = []

    async def fake_reload(entry_id: str) -> bool:
        reloads.append(entry_id)
        await asyncio.sleep(0.05)
        hass.states.async_set("remote.vu", "on")
        return True

    with patch.object(hass.config_entries, "async_reload", side_effect=fake_reload):
        await coordinator.async_start_activity("wz", "tv")
        # Its outlet came on: the integration was reloaded once after booting
        assert reloads == [apple.entry_id]
        reloads.clear()
        hass.states.async_set("remote.vu", "off")  # connection lost
        # Held button: several presses while reconnecting, one reload
        await asyncio.gather(send(hass, "channel_up"), send(hass, "channel_up"))

    assert reloads == [apple.entry_id]
    assert player_calls == [
        ("media_player.media_next_track", {"entity_id": VU}),
        ("media_player.media_next_track", {"entity_id": VU}),
    ]

    # Still not connected after the timeout: the caller gets an error
    hass.states.async_set("remote.vu", "off")
    coordinator.rooms["wz"]["devices"]["vu"]["ready"].update(timeout=1, reload_integration=False)
    with pytest.raises(HomeAssistantError) as err:
        await send(hass, "channel_up")
    assert err.value.translation_key == "device_not_ready"


async def test_quick_select_buttons(
    hass: HomeAssistant, devices: Devices, player_calls, hass_ws_client
) -> None:
    """A source button selects its source (an app) on its device."""
    data = remote_room()
    data["rooms"]["wz"]["activities"]["tv"]["remote"]["buttons"].append(
        {"device": "vu", "source": "Netflix", "icon": "mdi:netflix"}
    )
    coordinator = await setup(hass, devices, data)
    await coordinator.async_start_activity("wz", "tv")

    assert coordinator.room_view("wz")["remote"]["buttons"][2] == {
        "command": "select_source",
        "value": "Netflix",
        "name": "Netflix",
        "icon": "mdi:netflix",
        "device": "vu",
    }

    await send(hass, "select_source", value="Netflix", device="vu")
    # Sources that look like numbers keep their exact text
    await send(hass, "select_source", value="1", device="vu")
    await send(hass, "select_source", value="007", device="vu")
    await send(hass, "select_source", value="1.10", device="vu")
    # A number from YAML is passed on as its text
    await send(hass, "select_source", value=2, device="vu")
    assert player_calls == [
        ("media_player.select_source", {"entity_id": VU, "source": "Netflix"}),
        ("media_player.select_source", {"entity_id": VU, "source": "1"}),
        ("media_player.select_source", {"entity_id": VU, "source": "007"}),
        ("media_player.select_source", {"entity_id": VU, "source": "1.10"}),
        ("media_player.select_source", {"entity_id": VU, "source": "2"}),
    ]

    with pytest.raises(ServiceValidationError):
        await send(hass, "select_source", device="vu")


def test_settings_view() -> None:
    """Without settings: every list of the activity's media players; with
    them: the chosen ones, offering their favourites or the device's list."""
    data = living_room()
    data["rooms"]["wz"]["devices"]["plug"] = {"entity_id": "switch.plug"}
    data["rooms"]["wz"]["activities"]["tv"]["devices"].append("plug")
    room = validate_config(data)["rooms"]["wz"]
    known = {
        (ONKYO, "source"): ["SAT", "NET"],
        (ONKYO, "sound_mode"): ["THX", "STEREO", "DIRECT"],
        (VU, "source"): ["ZDF"],
    }

    def lists(entity_id: str, setting: str) -> list[str]:
        return known.get((entity_id, setting), [])

    tv = room["activities"]["tv"]
    assert [(s["device"], s["setting"], s["options"]) for s in settings_view(room, tv, lists)] == [
        ("onkyo", "source", ["SAT", "NET"]),
        ("onkyo", "sound_mode", ["THX", "STEREO", "DIRECT"]),
        ("vu", "source", ["ZDF"]),
    ]
    assert settings_view(room, tv, lists)[1] == {
        "device": "onkyo",
        "name": None,
        "device_entity_id": ONKYO,
        "label": None,
        "entity_id": ONKYO,
        "setting": "sound_mode",
        "attribute": "sound_mode",
        "command": "select_sound_mode",
        "options": ["THX", "STEREO", "DIRECT"],
    }

    tv["remote"]["settings"] = [
        {"device": "onkyo", "setting": "sound_mode", "options": ["DIRECT", "THX"]},
        {"device": "beamer", "setting": "source", "options": []},
    ]
    assert [(s["device"], s["setting"], s["options"]) for s in settings_view(room, tv, lists)] == [
        ("onkyo", "sound_mode", ["DIRECT", "THX"]),
        ("beamer", "source", []),
    ]
    tv["remote"]["settings"] = []
    assert settings_view(room, tv, lists) == []

    # An entity of the device: the card reads its state, the entity is the command
    tv["remote"]["settings"] = [
        {"device": "onkyo", "entity": "number.onkyo_bass", "name": "Bass", "options": []}
    ]
    assert settings_view(room, tv, lists) == [
        {
            "device": "onkyo",
            "name": None,
            "device_entity_id": ONKYO,
            "label": "Bass",
            "entity_id": "number.onkyo_bass",
            "setting": "entity",
            "attribute": None,
            "command": "number.onkyo_bass",
            "options": [],
        }
    ]


async def test_entity_settings(hass: HomeAssistant, devices: Devices, hass_ws_client) -> None:
    """A number, select or switch of a device is set with its entity ID as
    command; other entities are no commands."""
    calls: list[tuple[str, dict[str, Any]]] = []

    async def record(call: ServiceCall) -> None:
        calls.append((f"{call.domain}.{call.service}", dict(call.data)))

    data = remote_room()
    room = data["rooms"]["wz"]
    room["activities"]["musik"]["remote"] = {"settings": [
        {"device": "onkyo", "entity": "number.onkyo_bass"},
        {"device": "onkyo", "entity": "select.onkyo_dimmer", "options": ["Dim", "Off"]},
        {"device": "onkyo", "entity": "switch.onkyo_late_night"},
    ]}
    coordinator = await setup(hass, devices, data)
    await coordinator.async_start_activity("wz", "musik")
    # After the setup, which loads the select and switch components with their own actions
    for domain, service in (
        ("number", "set_value"), ("select", "select_option"),
        ("switch", "turn_on"), ("switch", "turn_off"),
    ):
        hass.services.async_register(domain, service, record)

    await send(hass, "number.onkyo_bass", value="-3", device="onkyo")
    await send(hass, "select.onkyo_dimmer", value="Dim", device="onkyo")
    await send(hass, "switch.onkyo_late_night", value="on", device="onkyo")
    await send(hass, "switch.onkyo_late_night", value=False, device="onkyo")
    assert calls == [
        ("number.set_value", {"entity_id": "number.onkyo_bass", "value": -3.0}),
        ("select.select_option", {"entity_id": "select.onkyo_dimmer", "option": "Dim"}),
        ("switch.turn_on", {"entity_id": "switch.onkyo_late_night"}),
        ("switch.turn_off", {"entity_id": "switch.onkyo_late_night"}),
    ]

    for command, value, device in (
        ("number.onkyo_bass", "loud", "onkyo"),  # not a number
        ("number.onkyo_bass", None, "onkyo"),  # no value
        ("number.onkyo_bass", 3, "beamer"),  # not a setting of that device
        ("number.other", 3, "onkyo"),  # not a setting at all
    ):
        with pytest.raises(ServiceValidationError):
            await send(hass, command, device=device, **({"value": value} if value is not None else {}))

    preview = await _preview(hass_ws_client, hass, room, "musik")
    assert preview["targets"]["number.onkyo_bass|onkyo"] == {
        "via": "entity", "action": "number.set_value", "entity_id": "number.onkyo_bass",
        "device": "onkyo", "ready": True,
    }


async def test_device_settings(
    hass: HomeAssistant, devices: Devices, player_calls, hass_storage
) -> None:
    """The card offers the source and sound mode of the running activity's
    media players, also while one is off, and sets them on the device."""
    hass.states.async_set(
        ONKYO, "on", {"source_list": ["SAT", "NET"], "sound_mode_list": ["THX", "STEREO"]}
    )
    coordinator = await setup(hass, devices, remote_room())
    await coordinator.async_start_activity("wz", "musik")

    settings = coordinator.room_view("wz")["remote"]["settings"]
    assert [(s["setting"], s["options"]) for s in settings] == [
        ("source", ["SAT", "NET"]),
        ("sound_mode", ["THX", "STEREO"]),
    ]

    # Off: the lists are gone from the state but remembered
    hass.states.async_set(ONKYO, "off", {})
    await hass.async_block_till_done()
    assert coordinator.room_view("wz")["remote"]["settings"] == settings

    # A new list reaches the card
    updates: list[int] = []
    coordinator.async_add_listener(lambda: updates.append(1))
    hass.states.async_set(ONKYO, "on", {"sound_mode_list": ["THX", "STEREO", "DIRECT"]})
    await hass.async_block_till_done()
    assert updates
    assert coordinator.room_view("wz")["remote"]["settings"][1]["options"] == [
        "THX", "STEREO", "DIRECT"
    ]

    await send(hass, "select_sound_mode", value="DIRECT", device="onkyo")
    assert player_calls == [
        ("media_player.select_sound_mode", {"entity_id": ONKYO, "sound_mode": "DIRECT"}),
    ]
    with pytest.raises(ServiceValidationError):
        await send(hass, "select_sound_mode", device="onkyo")


async def test_remote_entity_navigation(
    hass: HomeAssistant, devices: Devices, player_calls
) -> None:
    """Navigation keys go to the device's remote entity, named for its integration."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from homeassistant.helpers import entity_registry as er

    apple = MockConfigEntry(domain="apple_tv")
    apple.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "remote", "apple_tv", "atv", suggested_object_id="atv", config_entry=apple
    )
    data = living_room()
    room = data["rooms"]["wz"]
    room["devices"]["atv"] = {"entity_id": "media_player.atv", "remote_entity": "remote.atv"}
    room["activities"]["atv"] = {"name": "Apple TV", "devices": ["onkyo", "atv"]}
    hass.states.async_set("media_player.atv", "off")
    coordinator = await setup(hass, devices, data)

    validated = coordinator.rooms["wz"]
    assert routing(validated, validated["activities"]["atv"])["navigation"] == "atv"

    await coordinator.async_start_activity("wz", "atv")
    for key in ("up", "ok", "back", "menu"):
        await send(hass, key)
    # Not a navigation key: still the media player's own action
    await send(hass, "play_pause")

    assert player_calls == [
        ("remote.send_command", {"entity_id": "remote.atv", "command": "up"}),
        ("remote.send_command", {"entity_id": "remote.atv", "command": "select"}),
        ("remote.send_command", {"entity_id": "remote.atv", "command": "menu"}),
        ("remote.send_command", {"entity_id": "remote.atv", "command": "top_menu"}),
        ("media_player.media_play_pause", {"entity_id": "media_player.atv"}),
    ]
    view = coordinator.room_view("wz")
    assert view["remote"]["groups"]["navigation"]["commands"] == [
        "up", "down", "left", "right", "ok", "back", "menu", "home"
    ]


def test_remote_entity_must_be_a_remote() -> None:
    """remote_entity accepts remote entities only."""
    data = living_room()
    data["rooms"]["wz"]["devices"]["vu"]["remote_entity"] = "media_player.vu"
    with pytest.raises(vol.Invalid):
        validate_config(data)


async def _preview(hass_ws_client, hass: HomeAssistant, room: dict[str, Any], activity: str) -> dict:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "av_scenes/config/remote", "room": "wz", "config": room, "activity": activity}
    )
    return (await client.receive_json())["result"]


async def test_card_preview_is_the_card(
    hass: HomeAssistant, devices: Devices, player_calls, hass_ws_client
) -> None:
    """The preview shows what the card shows while the activity runs, and every
    button does what the preview says."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from homeassistant.helpers import entity_registry as er

    apple = MockConfigEntry(domain="apple_tv")
    apple.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "remote", "apple_tv", "atv", suggested_object_id="atv", config_entry=apple
    )
    data = remote_room()
    room = data["rooms"]["wz"]
    room["devices"]["atv"] = {"entity_id": "media_player.atv", "remote_entity": "remote.atv"}
    room["activities"]["tv"]["devices"].append("atv")
    room["activities"]["tv"]["remote"]["buttons"].append({"device": "atv", "source": "Netflix"})
    hass.states.async_set("media_player.atv", "off")
    hass.states.async_set(ONKYO, "off", {"sound_mode_list": ["THX", "STEREO"]})
    coordinator = await setup(hass, devices, data)
    await coordinator.async_start_activity("wz", "tv")

    preview = await _preview(hass_ws_client, hass, room, "tv")

    assert preview["error"] is None
    assert preview["view"]["remote"] == coordinator.room_view("wz")["remote"]
    assert preview["view"]["activities"] == coordinator.room_view("wz")["activities"]
    targets = preview["targets"]
    assert targets["volume_up|"] == {
        "via": "media_player", "action": "media_player.volume_up",
        "device": "onkyo", "entity_id": ONKYO, "ready": True,
    }
    assert targets["ok|"]["via"] == "remote" and targets["ok|"]["key"] == "select"
    assert targets["netflix|"] == {"via": "activity_commands", "device": None, "actions": ["test.key"]}
    assert targets["select_source|atv"]["action"] == "media_player.select_source"
    assert targets["select_sound_mode|onkyo"]["action"] == "media_player.select_sound_mode"
    # "guide" goes with the navigation to the Apple TV, which has no such key
    assert targets["guide|"]["via"] is None and targets["guide|"]["device"] == "atv"

    # Press every button the preview shows: the engine runs what it announced
    hass.states.async_set(ONKYO, "on", {"is_volume_muted": False})
    for key, target in targets.items():
        command, device = key.split("|")
        player_calls.clear()
        value = {"volume_set": 0.3, "select_source": "Netflix", "select_sound_mode": "THX"}.get(
            command
        )
        extra = {**({"device": device} if device else {}), **({"value": value} if value else {})}
        if target["via"] is None:
            # A button nothing handles: the preview says so, the action refuses it
            with pytest.raises(ServiceValidationError):
                await send(hass, command, **extra)
            continue
        await send(hass, command, **extra)
        called, data_ = player_calls[-1]
        if target["via"] in ("remote", "media_player"):
            assert called == target["action"], key
            assert data_["entity_id"] == target["entity_id"], key
        else:
            assert called == "test.key", key


async def test_card_preview_routes(
    hass: HomeAssistant, devices: Devices, hass_ws_client
) -> None:
    """Which device each group goes to, and why a group is missing."""
    data = remote_room()
    await setup(hass, devices, data)
    room = data["rooms"]["wz"]
    room["activities"]["tv"]["remote"].update(channels=None, transport="onkyo")

    preview = await _preview(hass_ws_client, hass, room, "tv")

    routes = {r["group"]: r for r in preview["routes"]}
    assert routes["volume"]["mode"] == "auto" and routes["volume"]["device"] == "onkyo"
    assert routes["channels"]["mode"] == "hidden" and routes["channels"]["commands"] == []
    assert routes["transport"]["mode"] == "set" and routes["transport"]["device"] == "onkyo"
    assert "channels" not in preview["view"]["remote"]["groups"]

    # Unsaved and invalid: the error, and an unknown activity
    room["activities"]["tv"]["remote"]["volume"] = "nope"
    assert (await _preview(hass_ws_client, hass, room, "tv"))["error"]["path"][-1] == "volume"
    assert (await _preview(hass_ws_client, hass, remote_room()["rooms"]["wz"], "kino"))[
        "error"
    ]["message"] == "Unknown activity"
