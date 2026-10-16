"""Tests for the activity engine."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .common import BEAMER, ONKYO, PLUG_BEAMER, PLUG_MM, VU, Devices, living_room, setup
from custom_components.av_scenes.const import DOMAIN
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
    assert devices.names()[-1] == ("homeassistant.turn_off", (PLUG_BEAMER, PLUG_MM))
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


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


async def test_stop_with_delay_after_off(hass: HomeAssistant, devices: Devices) -> None:
    """Reverse order, the beamer cools down, the power switches go last."""
    coordinator = await setup(hass, devices, living_room())
    await coordinator.async_start_activity("wz", "tv")
    devices.calls.clear()

    await coordinator.async_stop_activity("wz")

    assert devices.names() == [
        ("homeassistant.turn_off", (VU,)),
        ("homeassistant.turn_off", (BEAMER,)),
        ("homeassistant.turn_off", (ONKYO,)),
        ("homeassistant.turn_off", (PLUG_BEAMER, PLUG_MM)),
    ]
    assert devices.sleeps == [180]
    assert coordinator.activity_states["wz"] == "idle"


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
    assert ("homeassistant.turn_off", (PLUG_BEAMER, PLUG_MM)) in devices.names()


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
