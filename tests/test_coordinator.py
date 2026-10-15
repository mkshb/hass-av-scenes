"""Tests for the activity engine."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from custom_components.av_scenes.const import DOMAIN
from custom_components.av_scenes.coordinator import AVScenesCoordinator, _current_room

ONKYO = "media_player.onkyo_receiver"
BEAMER = "media_player.epson_ehtw7400"
VU = "media_player.vu_as2b_de"
PLUG_BEAMER = "switch.wz_steckdose_beamer_5_3_schwarz"
PLUG_MM = "switch.wz_steckdose_multimedia_5_4_grau"


def living_room(**overrides: Any) -> dict[str, Any]:
    """The target setup of the living room from the task description."""
    ready = {"timeout": 60, "reload_integration": True, "on_timeout": "continue"}
    room = {
        "name": "Wohnzimmer",
        "devices": {
            "onkyo": {
                "entity_id": ONKYO,
                "power_switch": PLUG_MM,
                "ready": {**ready, "on_timeout": "abort"},
            },
            "beamer": {
                "entity_id": BEAMER,
                "power_switch": PLUG_BEAMER,
                "ready": ready,
                "delay_after_off": 180,
            },
            "vu": {"entity_id": VU, "power_switch": PLUG_MM, "ready": ready},
        },
        "activities": {
            "tv": {
                "name": "TV",
                "devices": ["onkyo", "beamer", "vu"],
                "steps": [
                    {"type": "set_source", "device": "onkyo", "source": "SAT"},
                    {"type": "set_sound_mode", "device": "onkyo", "sound_mode": "THX"},
                    {"type": "set_volume", "device": "onkyo", "volume_level": 0.35},
                ],
                "on_start": [
                    {"action": "cover.close_cover", "target": {"entity_id": "cover.wz"}}
                ],
            },
            "musik": {
                "name": "Musik",
                "devices": ["onkyo"],
                "steps": [{"type": "set_source", "device": "onkyo", "source": "NET"}],
            },
        },
    }
    room.update(overrides)
    return {"rooms": {"wz": room}}


def _entities(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    return (value,) if isinstance(value, str) else tuple(value)


class Devices:
    """Fake devices: records the engine's service calls and updates states.

    The engine's calls are intercepted at AVScenesCoordinator._async_call;
    hook actions (run by the HA script engine) reach the mocked cover services.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.calls: list[tuple[str, tuple[str, ...], dict[str, Any]]] = []
        self.sleeps: list[float] = []
        for service in ("close_cover", "open_cover"):
            hass.services.async_register("cover", service, self._record)

    async def _record(self, call: ServiceCall) -> None:
        data = {k: v for k, v in call.data.items() if k != "entity_id"}
        self.calls.append(
            (f"{call.domain}.{call.service}", _entities(call.data.get("entity_id")), data)
        )

    async def engine_call(
        self,
        domain: str,
        service: str,
        data: dict[str, Any],
        context: Any,
        label: str,
        target: dict[str, Any] | None = None,
    ) -> None:
        entities = _entities(data.get("entity_id") or (target or {}).get("entity_id"))
        extra = {k: v for k, v in data.items() if k != "entity_id"}
        self.calls.append((f"{domain}.{service}", entities, extra))
        if domain == "homeassistant":
            for entity_id in entities:
                self.hass.states.async_set(entity_id, "on" if service == "turn_on" else "off")

    def names(self) -> list[tuple[str, tuple[str, ...]]]:
        return [(name, entities) for name, entities, _ in self.calls]


@pytest.fixture
async def devices(hass: HomeAssistant) -> Devices:
    """Fake devices, all powered off but present."""
    for entity_id in (ONKYO, BEAMER, VU, PLUG_BEAMER, PLUG_MM):
        hass.states.async_set(entity_id, "off")
    return Devices(hass)


async def setup(hass: HomeAssistant, devices: Devices, data: dict[str, Any]) -> AVScenesCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=1, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator: AVScenesCoordinator = hass.data[DOMAIN][entry.entry_id]

    async def fake_sleep(seconds: float) -> None:
        devices.sleeps.append(seconds)

    coordinator._async_sleep = fake_sleep  # type: ignore[method-assign]
    coordinator._async_call = devices.engine_call  # type: ignore[method-assign]
    return coordinator


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
    notifications = hass.data["persistent_notification"]
    assert any("aborted" in n["message"] for n in notifications.values())

    # A stop from the error state cleans up whatever was powered
    await coordinator.async_stop_activity("wz")
    assert coordinator.activity_states["wz"] == "idle"
    assert devices.names()[-1] == ("homeassistant.turn_off", (PLUG_BEAMER, PLUG_MM))


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
