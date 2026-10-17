"""Tests for the flow of an activity shown in the panel."""
from __future__ import annotations

import copy
from typing import Any

from homeassistant.core import HomeAssistant

from .common import (
    BEAMER,
    KITCHEN,
    ONKYO,
    PLUG_BEAMER,
    PLUG_MM,
    VU,
    Devices,
    living_room,
    setup,
)
from custom_components.av_scenes.control import action_names
from custom_components.av_scenes.flow import plan_start, plan_stop
from custom_components.av_scenes.model import validate_config


def _room(data: dict[str, Any]) -> dict[str, Any]:
    return validate_config(copy.deepcopy(data))["rooms"]["wz"]


def _calls(flow: dict[str, Any], *, background: bool = False) -> list[tuple[str, tuple[str, ...]]]:
    """The service calls a flow announces, in order: those the command runs
    itself, or the power cuts it leaves to the background."""
    calls = []
    for row in flow["rows"]:
        if row["kind"] == "hook" or "action" not in row:
            continue
        if row.get("background", False) != background:
            continue
        entities = row.get("entities") or [row["entity_id"]]
        calls.append((row["action"], tuple(entities)))
    return calls


def _assert_engine_follows(flow: dict[str, Any], devices: Devices) -> None:
    # Without the on_start / on_stop actions, which the script engine runs
    calls = [(name, entities) for name, entities in devices.names() if entities != ("cover.wz",)]
    # The fake sleep returns at once, so background cuts run in between
    background = _calls(flow, background=True)
    assert [call for call in calls if call not in background] == _calls(flow)
    assert sorted(call for call in calls if call in background) == sorted(background)


async def test_start_from_idle_matches_the_engine(hass: HomeAssistant, devices: Devices) -> None:
    data = living_room()
    coordinator = await setup(hass, devices, data)
    flow = plan_start(hass, "wz", _room(data), "tv")

    await coordinator.async_start_activity("wz", "tv")

    _assert_engine_follows(flow, devices)
    kinds = [row["kind"] for row in flow["rows"]]
    assert kinds[0] == "state" and kinds[-1] == "state"
    assert flow["rows"][-1]["state"] == "active"
    hook = next(row for row in flow["rows"] if row["kind"] == "hook")
    assert hook["actions"] == ["cover.close_cover"]
    # Every device's integration is reloaded after its outlet came on
    reloads = [row["entity_id"] for row in flow["rows"] if row["kind"] == "reload"]
    assert reloads == [ONKYO, BEAMER, VU]


async def test_switching_matches_the_engine(hass: HomeAssistant, devices: Devices) -> None:
    data = living_room()
    coordinator = await setup(hass, devices, data)
    await coordinator.async_start_activity("wz", "tv")
    devices.calls.clear()
    flow = plan_start(hass, "wz", _room(data), "musik", previous="tv")

    await coordinator.async_start_activity("wz", "musik")
    await hass.async_block_till_done()

    _assert_engine_follows(flow, devices)
    assert _calls(flow)[:3] == [
        ("homeassistant.turn_off", (VU,)),
        ("homeassistant.turn_off", (BEAMER,)),
        ("homeassistant.turn_on", (PLUG_MM,)),
    ]
    onkyo = [row for row in flow["rows"] if row.get("device") == "onkyo"]
    assert [row["kind"] for row in onkyo] == ["device", "already_on", "step"]
    cut = flow["rows"][-1]
    assert cut["kind"] == "outlets_off" and cut["background"]
    assert cut["entities"] == [PLUG_BEAMER] and cut["at"] == [180, 180]


async def test_stop_matches_the_engine(hass: HomeAssistant, devices: Devices) -> None:
    data = living_room()
    coordinator = await setup(hass, devices, data)
    await coordinator.async_start_activity("wz", "tv")
    devices.calls.clear()
    flow = plan_stop(hass, "wz", _room(data), "tv")

    await coordinator.async_stop_activity("wz")
    await hass.async_block_till_done()

    _assert_engine_follows(flow, devices)
    states = [row["state"] for row in flow["rows"] if row["kind"] == "state"]
    assert states == ["stopping", "idle"]
    assert flow["rows"][-1]["at"] == [180, 180]


async def test_times_match_the_engine(hass: HomeAssistant, devices: Devices) -> None:
    """The earliest times are the engine's waits when every device is ready at once."""
    data = living_room()
    room = data["rooms"]["wz"]
    room["devices"]["beamer"]["delay_after_power"] = 20
    room["devices"]["onkyo"]["delay_after_on"] = 5
    room["devices"]["vu"]["delay_after_power"] = 8
    room["activities"]["tv"]["steps"][0]["delay_after"] = 2
    coordinator = await setup(hass, devices, data)
    flow = plan_start(hass, "wz", _room(data), "tv")

    await coordinator.async_start_activity("wz", "tv")

    # Onkyo 5 s, projector boots until 20 s (the VU+ is up by then), 2 s after a step
    assert flow["done"][0] == devices.clock == 22
    # Latest: every readiness check takes its 60 s; the boot times pass meanwhile
    assert flow["done"][1] == 60 + 5 + 60 + 60 + 2
    boot = [row for row in flow["rows"] if row["kind"] == "boot"]
    # The beamer boots from 5 s (after the Onkyo) until 20 s; the VU+ is up by then
    assert [(row["device"], row["at"]) for row in boot] == [("beamer", [5, 65]), ("vu", [20, 125])]


async def test_shared_outlet_is_named(hass: HomeAssistant, devices: Devices) -> None:
    data = living_room()
    others = {"kueche": {"name": "Küche", "devices": {"radio": {"entity_id": KITCHEN, "power_switch": PLUG_MM}}}}
    flow = plan_stop(hass, "wz", _room(data), "tv", others)

    now = next(row for row in flow["rows"] if row["kind"] == "outlets_off")
    assert now["entities"] == [PLUG_MM]
    assert now["unless_rooms"] == ["Küche"]


async def test_devices_that_cannot_be_switched_are_marked(
    hass: HomeAssistant, devices: Devices
) -> None:
    hass.states.async_set(ONKYO, "on", {"supported_features": 0})
    flow = plan_stop(hass, "wz", _room(living_room()), "tv")

    onkyo = next(row for row in flow["rows"] if row.get("device") == "onkyo")
    assert onkyo["skip"] == "cannot_switch"
    assert "action" not in onkyo


def test_action_names() -> None:
    actions = [
        {"if": [{"condition": "state"}], "then": [{"action": "cover.close_cover"}]},
        {"action": "light.turn_on"},
        {"delay": 3},
        {"choose": [{"sequence": [{"action": "light.turn_on"}, {"action": "script.popcorn"}]}]},
    ]
    assert action_names(actions) == ["cover.close_cover", "light.turn_on", "script.popcorn"]


async def test_websocket_flow(hass: HomeAssistant, devices: Devices, hass_ws_client) -> None:
    data = living_room()
    await setup(hass, devices, data)
    client = await hass_ws_client(hass)
    room = data["rooms"]["wz"]

    await client.send_json_auto_id(
        {"type": "av_scenes/config/flow", "room": "wz", "config": room, "activity": "tv"}
    )
    result = (await client.receive_json())["result"]
    assert result["error"] is None
    assert result["rows"][-1] == {"kind": "state", "at": [0, 180], "state": "active"}

    await client.send_json_auto_id(
        {"type": "av_scenes/config/flow", "room": "wz", "config": room, "activity": "tv", "mode": "stop"}
    )
    result = (await client.receive_json())["result"]
    assert [row["state"] for row in result["rows"] if row["kind"] == "state"] == ["stopping", "idle"]

    # Unsaved and invalid: the error instead of a flow
    broken = copy.deepcopy(room)
    broken["activities"]["tv"]["devices"].append("nope")
    await client.send_json_auto_id(
        {"type": "av_scenes/config/flow", "room": "wz", "config": broken, "activity": "tv"}
    )
    result = (await client.receive_json())["result"]
    assert result["error"]["path"] == ["rooms", "wz", "activities", "tv", "devices", "3"]

    await client.send_json_auto_id(
        {"type": "av_scenes/config/flow", "room": "wz", "config": room, "activity": "tv", "from": "kino"}
    )
    result = (await client.receive_json())["result"]
    assert result["error"]["message"] == "Unknown activity"
