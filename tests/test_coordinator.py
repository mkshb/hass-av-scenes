"""Tests for the activity engine."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

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
from custom_components.av_scenes.const import DOMAIN, SIGNAL_ROOMS_UPDATED
from custom_components.av_scenes.coordinator import AVScenesCoordinator, _current_room


async def test_start_order(hass: HomeAssistant, devices: Devices) -> None:
    """Power first, then devices in order, then steps and hooks."""
    coordinator = await setup(hass, devices, living_room())

    await coordinator.async_start_activity("wz", "TV")  # by display name

    assert devices.names() == [
        ("homeassistant.turn_on", (PLUG_MM, PLUG_BEAMER)),
        ("cover.close_cover", ("cover.wz",)),
        ("homeassistant.turn_on", (ONKYO,)),
        ("homeassistant.turn_on", (BEAMER,)),
        ("homeassistant.turn_on", (VU,)),
        ("media_player.select_source", (ONKYO,)),
        ("media_player.select_sound_mode", (ONKYO,)),
        ("media_player.volume_set", (ONKYO,)),
    ]
    assert coordinator.activity_states["wz"] == "active"
    assert coordinator.active_activities["wz"] == "tv"
    assert coordinator.runtime("wz").warnings == []


async def test_device_already_on_is_not_switched(hass: HomeAssistant, devices: Devices) -> None:
    """A device that is on gets no turn_on and no warm-up delay."""
    data = living_room()
    data["rooms"]["wz"]["devices"]["onkyo"]["delay_after_on"] = 5
    coordinator = await setup(hass, devices, data)
    hass.states.async_set(ONKYO, "on")

    await coordinator.async_start_activity("wz", "musik")

    assert ("homeassistant.turn_on", (ONKYO,)) not in devices.names()
    assert devices.sleeps == []


async def test_wait_available_after_reload(hass: HomeAssistant, devices: Devices) -> None:
    """An unavailable device comes up after its integration was reloaded once."""
    other = MockConfigEntry(domain="onkyo")
    other.add_to_hass(hass)
    hass.states.async_remove(ONKYO)
    er.async_get(hass).async_get_or_create(
        "media_player", "onkyo", "x", suggested_object_id="onkyo_receiver",
        config_entry=other,
    )
    coordinator = await setup(hass, devices, living_room())
    hass.states.async_set(ONKYO, "unavailable")
    reloads: list[str] = []

    async def fake_reload(entry_id: str) -> bool:
        reloads.append(entry_id)
        await asyncio.sleep(0)
        hass.states.async_set(ONKYO, "off")
        return True

    with patch.object(hass.config_entries, "async_reload", side_effect=fake_reload):
        await coordinator.async_start_activity("wz", "musik")

    assert reloads == [other.entry_id]
    assert ("homeassistant.turn_on", (ONKYO,)) in devices.names()
    assert coordinator.activity_states["wz"] == "active"


async def test_hanging_reload_does_not_hold_up_the_start(
    hass: HomeAssistant, devices: Devices
) -> None:
    """A reload that never finishes counts against the readiness timeout."""
    other = MockConfigEntry(domain="onkyo")
    other.add_to_hass(hass)
    hass.states.async_remove(ONKYO)
    er.async_get(hass).async_get_or_create(
        "media_player", "onkyo", "x", suggested_object_id="onkyo_receiver",
        config_entry=other,
    )
    data = living_room()
    data["rooms"]["wz"]["devices"]["onkyo"]["ready"]["timeout"] = 1
    coordinator = await setup(hass, devices, data)
    hass.states.async_set(ONKYO, "off")
    never = asyncio.Event()

    async def hanging_reload(entry_id: str) -> bool:
        await never.wait()
        return True

    with patch.object(hass.config_entries, "async_reload", side_effect=hanging_reload):
        async with asyncio.timeout(5):
            await coordinator.async_start_activity("wz", "musik")

    assert coordinator.activity_states["wz"] == "active"
    assert ("homeassistant.turn_on", (ONKYO,)) in devices.names()
    assert any("did not finish within 1 s" in w for w in coordinator.runtime("wz").warnings)
    never.set()
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_wait_available_immediate(hass: HomeAssistant, devices: Devices) -> None:
    """An available device is not reloaded."""
    coordinator = await setup(hass, devices, living_room())
    with patch.object(hass.config_entries, "async_reload") as reload:
        await coordinator.async_start_activity("wz", "musik")
    reload.assert_not_called()


async def test_wait_available_timeout_abort(hass: HomeAssistant, devices: Devices) -> None:
    """on_timeout abort: no further steps, room in error, never active."""
    data = living_room()
    data["rooms"]["wz"]["devices"]["onkyo"]["ready"].update(
        timeout=1, reload_integration=False
    )
    coordinator = await setup(hass, devices, data)
    hass.states.async_remove(ONKYO)

    await coordinator.async_start_activity("wz", "tv")

    assert coordinator.activity_states["wz"] == "error"
    assert "not available after 1 s" in coordinator.runtime("wz").error
    assert ("media_player.select_source", (ONKYO,)) not in devices.names()
    assert ("homeassistant.turn_on", (BEAMER,)) not in devices.names()
    issue_id = f"activity_aborted_{coordinator.entry.entry_id}_wz"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_placeholders["activity"] == "TV"

    # A stop from the error state cleans up whatever was powered
    await coordinator.async_stop_activity("wz")
    assert coordinator.activity_states["wz"] == "idle"
    await hass.async_block_till_done()
    assert _plugs_cut(devices) == {PLUG_BEAMER, PLUG_MM}
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_unexpected_failure_puts_the_room_in_error(
    hass: HomeAssistant, devices: Devices
) -> None:
    """A bug while starting or stopping does not leave the room starting or stopping."""
    coordinator = await setup(hass, devices, living_room())

    async def broken_step(*args, **kwargs) -> None:
        raise RuntimeError("step exploded")

    with patch.object(coordinator, "_async_execute_step", broken_step):
        await coordinator.async_start_activity("wz", "tv")

    assert coordinator.activity_states["wz"] == "error"
    assert coordinator.runtime("wz").error == "step exploded"
    issue_id = f"activity_aborted_{coordinator.entry.entry_id}_wz"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    async def broken_power_off(*args) -> None:
        raise RuntimeError("switch exploded")

    with patch.object(coordinator, "_async_power_off", broken_power_off):
        await coordinator.async_stop_activity("wz")

    assert coordinator.activity_states["wz"] == "error"
    assert coordinator.runtime("wz").error == "switch exploded"

    # Stopping again works once the cause is gone
    await coordinator.async_stop_activity("wz")
    assert coordinator.activity_states["wz"] == "idle"


async def test_wait_available_step_timeout_continue(
    hass: HomeAssistant, devices: Devices
) -> None:
    """on_timeout continue: the activity goes on."""
    data = living_room()
    data["rooms"]["wz"]["activities"]["musik"]["steps"].insert(
        0,
        {"type": "wait_available", "entity_id": "media_player.nope", "timeout": 1,
         "on_timeout": "continue"},
    )
    coordinator = await setup(hass, devices, data)

    await coordinator.async_start_activity("wz", "musik")

    assert coordinator.activity_states["wz"] == "active"
    assert ("media_player.select_source", (ONKYO,)) in devices.names()


def _plugs_cut(devices: Devices) -> set[str]:
    """Power switches turned off, in one call or several."""
    return {
        entity
        for name, entities in devices.names()
        if name == "homeassistant.turn_off"
        for entity in entities
        if entity in (PLUG_BEAMER, PLUG_MM)
    }

async def test_stop_with_delay_after_off(hass: HomeAssistant, devices: Devices) -> None:
    """Reverse order; the room is idle once the devices are off. The plug without
    cool-down goes at once, the beamer's after its cool-down in the background."""
    coordinator = await setup(hass, devices, living_room())
    await coordinator.async_start_activity("wz", "tv")
    devices.calls.clear()
    devices.sleeps.clear()

    await coordinator.async_stop_activity("wz")

    assert coordinator.activity_states["wz"] == "idle"
    assert devices.names()[:4] == [
        ("homeassistant.turn_off", (VU,)),
        ("homeassistant.turn_off", (BEAMER,)),
        ("homeassistant.turn_off", (ONKYO,)),
        ("homeassistant.turn_off", (PLUG_MM,)),
    ]

    await hass.async_block_till_done()
    assert devices.names()[4:] == [("homeassistant.turn_off", (PLUG_BEAMER,))]
    assert devices.sleeps == [180]


async def test_start_during_cool_down_keeps_the_plug(
    hass: HomeAssistant, devices: Devices
) -> None:
    """A start while the beamer cools down cancels the cut of its plug."""
    coordinator = await setup(hass, devices, living_room())
    await coordinator.async_start_activity("wz", "tv")
    cut = asyncio.Event()

    async def slow_sleep(seconds: float) -> None:
        devices.sleeps.append(seconds)
        await cut.wait()

    coordinator._async_sleep = slow_sleep  # type: ignore[method-assign]
    await coordinator.async_stop_activity("wz")
    assert coordinator.activity_states["wz"] == "idle"
    assert PLUG_BEAMER in coordinator.runtime("wz").pending_cuts

    devices.calls.clear()
    await coordinator.async_start_activity("wz", "tv")
    cut.set()
    await hass.async_block_till_done()

    assert ("homeassistant.turn_off", (PLUG_BEAMER,)) not in devices.names()
    assert hass.states.get(PLUG_BEAMER).state == "on"


async def test_smart_switching(hass: HomeAssistant, devices: Devices) -> None:
    """TV -> Musik: beamer and VU off, beamer plug cut after the cool-down."""
    coordinator = await setup(hass, devices, living_room())
    await coordinator.async_start_activity("wz", "tv")
    devices.calls.clear()

    await coordinator.async_start_activity("wz", "musik")
    await hass.async_block_till_done()

    names = devices.names()
    assert ("homeassistant.turn_off", (VU,)) in names
    assert ("homeassistant.turn_off", (BEAMER,)) in names
    assert ("homeassistant.turn_off", (ONKYO,)) not in names
    # The multimedia plug still feeds the Onkyo
    assert ("homeassistant.turn_off", (PLUG_MM,)) not in names
    assert ("homeassistant.turn_off", (PLUG_BEAMER,)) in names
    assert 180 in devices.sleeps
    assert coordinator.active_activities["wz"] == "musik"


def _with_kitchen(delay_after_off: float = 0) -> dict:
    """Living room plus a kitchen whose speaker hangs on the multimedia plug."""
    data = living_room()
    data["rooms"]["kueche"] = {
        "name": "Küche",
        "devices": {
            "radio": {
                "entity_id": KITCHEN,
                "power_switch": PLUG_MM,
                "delay_after_off": delay_after_off,
            }
        },
        "activities": {"radio": {"name": "Radio", "devices": ["radio"]}},
    }
    return data


async def test_stop_keeps_a_plug_another_room_uses(
    hass: HomeAssistant, devices: Devices
) -> None:
    """The multimedia plug stays on while the kitchen radio runs."""
    hass.states.async_set(KITCHEN, "off")
    coordinator = await setup(hass, devices, _with_kitchen())
    await coordinator.async_start_activity("kueche", "radio")
    await coordinator.async_start_activity("wz", "tv")
    devices.calls.clear()

    await coordinator.async_stop_activity("wz")
    await hass.async_block_till_done()

    assert _plugs_cut(devices) == {PLUG_BEAMER}
    assert coordinator.activity_states["kueche"] == "active"

    await coordinator.async_stop_activity("kueche")
    await hass.async_block_till_done()
    assert _plugs_cut(devices) == {PLUG_BEAMER, PLUG_MM}


async def test_cool_down_keeps_a_plug_another_room_started(
    hass: HomeAssistant, devices: Devices
) -> None:
    """A room started during another room's cool-down keeps the shared plug."""
    hass.states.async_set(KITCHEN, "off")
    coordinator = await setup(hass, devices, _with_kitchen(delay_after_off=30))
    await coordinator.async_start_activity("kueche", "radio")
    cut = asyncio.Event()

    async def slow_sleep(seconds: float) -> None:
        devices.sleeps.append(seconds)
        await cut.wait()

    coordinator._async_sleep = slow_sleep  # type: ignore[method-assign]
    await coordinator.async_stop_activity("kueche")
    assert PLUG_MM in coordinator.runtime("kueche").pending_cuts

    coordinator._async_sleep = devices.fake_sleep  # type: ignore[method-assign]
    await coordinator.async_start_activity("wz", "musik")
    devices.calls.clear()
    cut.set()
    await hass.async_block_till_done()

    assert PLUG_MM not in _plugs_cut(devices)
    assert hass.states.get(PLUG_MM).state == "on"


async def test_last_command_wins(hass: HomeAssistant, devices: Devices) -> None:
    """Start, stop, start in quick succession: the room ends up running."""
    data = living_room()
    data["rooms"]["wz"]["devices"]["onkyo"]["delay_after_on"] = 5
    coordinator = await setup(hass, devices, data)
    warm_up = asyncio.Event()

    async def slow_sleep(seconds: float) -> None:
        await warm_up.wait()

    coordinator._async_sleep = slow_sleep  # type: ignore[method-assign]
    first = hass.async_create_task(coordinator.async_start_activity("wz", "tv"))
    await asyncio.sleep(0.01)
    assert coordinator.activity_states["wz"] == "starting"

    # The stop is still waiting for the cancelled start when the next start comes
    stop = hass.async_create_task(coordinator.async_stop_activity("wz"))
    again = hass.async_create_task(coordinator.async_start_activity("wz", "tv"))
    warm_up.set()
    async with asyncio.timeout(2):
        await asyncio.gather(first, stop, again)

    assert coordinator.activity_states["wz"] == "active"
    assert coordinator.active_activities["wz"] == "tv"


async def test_stop_cancels_running_start(hass: HomeAssistant, devices: Devices) -> None:
    """A stop during a long readiness wait does not wait for the start."""
    coordinator = await setup(hass, devices, living_room())
    hass.states.async_remove(ONKYO)

    start = hass.async_create_task(coordinator.async_start_activity("wz", "tv"))
    await asyncio.sleep(0.05)
    assert coordinator.activity_states["wz"] == "starting"

    async with asyncio.timeout(2):
        await coordinator.async_stop_activity("wz")
        await start

    assert coordinator.activity_states["wz"] == "idle"
    await hass.async_block_till_done()
    assert _plugs_cut(devices) == {PLUG_BEAMER, PLUG_MM}


async def test_toggle(hass: HomeAssistant, devices: Devices) -> None:
    """Toggle starts the last activity, or stops."""
    coordinator = await setup(hass, devices, living_room())
    await coordinator.async_start_activity("wz", "musik")
    await coordinator.async_toggle_activity("wz")
    assert coordinator.activity_states["wz"] == "idle"
    await coordinator.async_toggle_activity("wz")
    assert coordinator.active_activities["wz"] == "musik"


async def test_default_activity(hass: HomeAssistant, devices: Devices) -> None:
    """A configured default activity wins over the last used one."""
    coordinator = await setup(hass, devices, living_room(default_activity="musik"))
    await coordinator.async_start_activity("wz", "tv")
    await coordinator.async_toggle_activity("wz")
    assert coordinator.activity_states["wz"] == "idle"
    assert coordinator.default_activity("wz") == "musik"
    await coordinator.async_toggle_activity("wz")
    assert coordinator.active_activities["wz"] == "musik"


async def test_state_restored(hass: HomeAssistant, devices: Devices, hass_storage) -> None:
    """The running activity survives a restart; an interrupted start is an error."""
    hass_storage["av_scenes.test_entry.state"] = {
        "version": 1,
        "data": {"rooms": {"wz": {"activity": "tv", "state": "starting",
                                  "last_activity": "musik"}}},
    }
    entry = MockConfigEntry(
        domain=DOMAIN, version=2, minor_version=1, data=living_room(), entry_id="test_entry"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator: AVScenesCoordinator = hass.data[DOMAIN][entry.entry_id]

    assert coordinator.activity_states["wz"] == "error"
    assert coordinator.active_activities["wz"] == "tv"
    assert coordinator.default_activity("wz") == "musik"


async def test_missing_entity_repair_issue(hass: HomeAssistant, devices: Devices) -> None:
    """A wrong entity_id raises a repair issue."""
    data = living_room()
    data["rooms"]["wz"]["devices"]["beamer"]["entity_id"] = "media_player.epson_beamer"
    await setup(hass, devices, data)

    issues = [
        issue for (domain, _), issue in ir.async_get(hass).issues.items() if domain == DOMAIN
    ]
    assert len(issues) == 1
    assert issues[0].translation_placeholders["entity_id"] == "media_player.epson_beamer"


async def test_invalid_config_fails_setup(hass: HomeAssistant, devices: Devices) -> None:
    """An invalid configuration is reported instead of half-loaded."""
    data = living_room()
    data["rooms"]["wz"]["activities"]["tv"]["devices"].append("nope")
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=1, data=data)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_service_call_is_blocking_with_timeout(hass: HomeAssistant) -> None:
    """The engine waits for a service, but not forever."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=1, data={"rooms": {}})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator: AVScenesCoordinator = hass.data[DOMAIN][entry.entry_id]
    finished: list[str] = []

    async def slow(call: ServiceCall) -> None:
        await asyncio.sleep(0.05 if call.data.get("fast") else 10)
        finished.append(call.service)

    hass.services.async_register("test", "fast", slow)
    hass.services.async_register("test", "slow", slow)
    coordinator.service_timeout = 0.2
    token = _current_room.set(coordinator.runtime("r"))
    try:
        await coordinator._async_call("test", "fast", {"fast": True}, Context(), "fast")
        assert finished == ["fast"]  # blocking: done when the call returns

        await coordinator._async_call("test", "slow", {}, Context(), "slow")
    finally:
        _current_room.reset(token)
    assert finished == ["fast"]
    assert "did not finish within 0.2 s" in coordinator.runtime("r").warnings[0]


async def test_delay_after_power(hass: HomeAssistant, devices: Devices) -> None:
    """Boot time after the power switch, shared by devices on the same switch."""
    data = living_room()
    room = data["rooms"]["wz"]
    for device in room["devices"].values():
        device.pop("ready", None)
    room["devices"]["onkyo"]["delay_after_power"] = 15
    room["devices"]["vu"]["delay_after_power"] = 20  # same switch as the Onkyo
    room["devices"]["beamer"]["delay_after_power"] = 5  # waited off by then
    coordinator = await setup(hass, devices, data)

    await coordinator.async_start_activity("wz", "tv")

    # Onkyo waits 15 s; by then the beamer has booted, the VU+ needs 5 s more
    assert devices.sleeps == [15, 5]
    assert devices.names().index(("homeassistant.turn_on", (PLUG_MM, PLUG_BEAMER))) < (
        devices.names().index(("homeassistant.turn_on", (ONKYO,)))
    )


async def test_delay_after_power_skipped_when_powered(
    hass: HomeAssistant, devices: Devices
) -> None:
    """No boot time when the power switch was already on."""
    data = living_room()
    data["rooms"]["wz"]["devices"]["onkyo"]["delay_after_power"] = 15
    coordinator = await setup(hass, devices, data)
    hass.states.async_set(PLUG_MM, "on")

    await coordinator.async_start_activity("wz", "musik")

    assert devices.sleeps == []


async def test_ready_waits_for_state_of_other_entity(
    hass: HomeAssistant, devices: Devices
) -> None:
    """An Apple TV reports off while disconnected; its remote tells the truth."""
    apple = MockConfigEntry(domain="apple_tv")
    apple.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "remote", "apple_tv", "x", suggested_object_id="vu", config_entry=apple
    )
    data = living_room()
    data["rooms"]["wz"]["devices"]["vu"]["ready"] = {
        "entity_id": "remote.vu", "state": "on", "timeout": 5,
        "reload_integration": True, "on_timeout": "continue",
    }
    hass.states.async_set("remote.vu", "off")
    coordinator = await setup(hass, devices, data)
    order: list[str] = []

    async def fake_reload(entry_id: str) -> bool:
        await asyncio.sleep(0.05)
        order.append("reloaded")
        hass.states.async_set("remote.vu", "on")
        return True

    with patch.object(hass.config_entries, "async_reload", side_effect=fake_reload):
        await coordinator.async_start_activity("wz", "tv")
        await hass.async_block_till_done()

    # The VU+ is switched on only once its remote is connected
    names = devices.names()
    assert order == ["reloaded"]
    assert ("homeassistant.turn_on", (VU,)) in names
    assert coordinator.activity_states["wz"] == "active"


async def test_players_without_power_control_are_not_switched(
    hass: HomeAssistant, devices: Devices
) -> None:
    """A speaker that cannot be turned on or off gets no such call."""
    from homeassistant.components.media_player import MediaPlayerEntityFeature

    data = living_room()
    room = data["rooms"]["wz"]
    room["devices"]["sonos"] = {"entity_id": "media_player.sonos"}
    room["activities"]["musik"]["devices"].append("sonos")
    features = int(MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.VOLUME_SET)
    hass.states.async_set("media_player.sonos", "idle", {"supported_features": features})
    coordinator = await setup(hass, devices, data)

    await coordinator.async_start_activity("wz", "musik")
    await coordinator.async_stop_activity("wz")

    assert not [c for c in devices.names() if "media_player.sonos" in c[1]]


async def test_reload_after_power_on_and_unreachable_device(
    hass: HomeAssistant, devices: Devices
) -> None:
    """After its outlet came on, a device's integration is reloaded even if it
    still reports a stale "off"; a device its integration reports unreachable is
    not switched on, and the activity says so."""
    from unittest.mock import MagicMock, patch

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.entity_component import DATA_INSTANCES

    epson = MockConfigEntry(domain="epson_projector_link")
    epson.add_to_hass(hass)
    hass.states.async_remove(BEAMER)  # free the entity ID for the registry
    er.async_get(hass).async_get_or_create(
        "media_player", "epson_projector_link", "beamer",
        suggested_object_id="epson_ehtw7400", config_entry=epson,
    )
    hass.states.async_set(BEAMER, "off")  # stale: the projector has no power
    data = living_room()
    data["rooms"]["wz"]["devices"]["beamer"]["ready"]["timeout"] = 1
    coordinator = await setup(hass, devices, data)
    reloads: list[str] = []

    async def fake_reload(entry_id: str) -> bool:
        reloads.append(entry_id)
        return True

    stale = MagicMock(available=False)
    component = MagicMock()
    component.get_entity.side_effect = lambda e: stale if e == BEAMER else None
    hass.data.setdefault(DATA_INSTANCES, {})["media_player"] = component
    with patch.object(hass.config_entries, "async_reload", side_effect=fake_reload):
        await coordinator.async_start_activity("wz", "tv")

    # The stale "off" counted as ready, but the integration was reloaded anyway
    assert epson.entry_id in reloads
    assert ("homeassistant.turn_on", (BEAMER,)) not in devices.names()
    assert any(BEAMER in w for w in coordinator.runtime("wz").warnings)


def _record_current(hass: HomeAssistant, coordinator: AVScenesCoordinator) -> list[dict]:
    """What the card is told the room is busy with, each time it changes."""
    seen: list[dict] = []

    def changed() -> None:
        current = coordinator.room_view("wz")["current"]
        if current and (not seen or seen[-1] != current):
            seen.append(current)

    async_dispatcher_connect(hass, SIGNAL_ROOMS_UPDATED, changed)
    return seen


async def test_start_tells_what_it_waits_for(hass: HomeAssistant, devices: Devices) -> None:
    """Boot time, warm-up, steps and waits, with the device and when a wait ends."""
    data = living_room()
    room = data["rooms"]["wz"]
    room["devices"]["beamer"]["delay_after_power"] = 20
    room["devices"]["beamer"]["name"] = "Beamer"
    room["devices"]["onkyo"]["delay_after_on"] = 5
    room["activities"]["tv"]["steps"][2]["delay_after"] = 2
    coordinator = await setup(hass, devices, data)
    seen = _record_current(hass, coordinator)
    before = dt_util.utcnow()

    await coordinator.async_start_activity("wz", "tv")

    assert [(c["kind"], c["name"]) for c in seen] == [
        ("power_on", None),
        ("turn_on", "onkyo receiver"),
        ("warm_up", "onkyo receiver"),
        ("boot", "Beamer"),
        ("turn_on", "Beamer"),
        ("turn_on", "vu as2b de"),
        ("step", "onkyo receiver"),
        ("step", "onkyo receiver"),
        ("step", "onkyo receiver"),
        ("wait", None),
    ]
    boot = seen[3]
    # 20 s from switching the outlets on, 5 s of them already gone for the Onkyo
    until = dt_util.parse_datetime(boot["until"])
    assert 14 <= (until - before).total_seconds() <= 16
    assert seen[6] == {"kind": "step", "name": "onkyo receiver", "step": 1, "steps": 3, "step_type": "set_source"}
    assert seen[9]["step"] == 3 and "until" in seen[9]
    # Done: nothing to show any more
    assert coordinator.room_view("wz")["current"] is None


async def test_start_tells_which_device_it_waits_for(
    hass: HomeAssistant, devices: Devices
) -> None:
    """While the readiness check waits, the card knows for whom and how long at most."""
    data = living_room()
    data["rooms"]["wz"]["devices"]["vu"]["ready"]["reload_integration"] = False
    coordinator = await setup(hass, devices, data)
    hass.states.async_set(VU, "unavailable")

    start = hass.async_create_task(coordinator.async_start_activity("wz", "tv"))
    await asyncio.sleep(0.05)
    current = coordinator.room_view("wz")["current"]
    assert current["kind"] == "ready" and current["name"] == "vu as2b de"
    remaining = (dt_util.parse_datetime(current["until"]) - dt_util.utcnow()).total_seconds()
    assert 55 < remaining <= 60

    hass.states.async_set(VU, "off")
    async with asyncio.timeout(2):
        await start
    assert coordinator.activity_states["wz"] == "active"
    assert coordinator.room_view("wz")["current"] is None


async def test_stop_tells_what_it_switches_off(hass: HomeAssistant, devices: Devices) -> None:
    coordinator = await setup(hass, devices, living_room())
    await coordinator.async_start_activity("wz", "tv")
    seen = _record_current(hass, coordinator)

    await coordinator.async_stop_activity("wz")

    assert [(c["kind"], c["name"]) for c in seen] == [
        ("turn_off", "vu as2b de"),
        ("turn_off", "epson ehtw7400"),
        ("turn_off", "onkyo receiver"),
        ("power_off", None),
    ]
    assert coordinator.room_view("wz")["current"] is None


async def test_card_shows_the_cool_down(hass: HomeAssistant, devices: Devices) -> None:
    """After a stop the card shows who cools down and when the power goes off."""
    coordinator = await setup(hass, devices, living_room())
    await coordinator.async_start_activity("wz", "tv")
    cut = asyncio.Event()

    async def slow_sleep(seconds: float) -> None:
        await cut.wait()

    coordinator._async_sleep = slow_sleep  # type: ignore[method-assign]
    before = dt_util.utcnow()
    await coordinator.async_stop_activity("wz")

    view = coordinator.room_view("wz")
    assert view["state"] == "idle"
    [cooling] = view["cooling"]
    assert cooling["outlet"] == "wz steckdose beamer 5 3 schwarz"
    assert cooling["names"] == ["epson ehtw7400"]
    left = (dt_util.parse_datetime(cooling["until"]) - before).total_seconds()
    assert 179 <= left <= 181

    updates: list[list] = []
    async_dispatcher_connect(
        hass, SIGNAL_ROOMS_UPDATED, lambda: updates.append(coordinator.room_view("wz")["cooling"])
    )
    cut.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator.room_view("wz")["cooling"] == []
    assert updates and updates[-1] == []


async def test_start_during_cool_down_ends_it(hass: HomeAssistant, devices: Devices) -> None:
    coordinator = await setup(hass, devices, living_room())
    await coordinator.async_start_activity("wz", "tv")
    cut = asyncio.Event()

    async def slow_sleep(seconds: float) -> None:
        await cut.wait()

    coordinator._async_sleep = slow_sleep  # type: ignore[method-assign]
    await coordinator.async_stop_activity("wz")
    assert coordinator.room_view("wz")["cooling"]

    coordinator._async_sleep = devices.fake_sleep  # type: ignore[method-assign]
    await coordinator.async_start_activity("wz", "tv")
    assert coordinator.room_view("wz")["cooling"] == []
    cut.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator.room_view("wz")["cooling"] == []


async def test_switching_shows_the_cool_down(hass: HomeAssistant, devices: Devices) -> None:
    """TV -> Musik: the projector cools down while Musik already runs."""
    coordinator = await setup(hass, devices, living_room())
    await coordinator.async_start_activity("wz", "tv")
    cut = asyncio.Event()

    async def slow_sleep(seconds: float) -> None:
        await cut.wait()

    coordinator._async_sleep = slow_sleep  # type: ignore[method-assign]
    await coordinator.async_start_activity("wz", "musik")

    view = coordinator.room_view("wz")
    assert view["state"] == "active"
    assert [c["names"] for c in view["cooling"]] == [["epson ehtw7400"]]
    cut.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator.room_view("wz")["cooling"] == []
