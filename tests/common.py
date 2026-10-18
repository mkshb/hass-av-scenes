"""Shared test helpers: the living room setup and fake devices."""
from __future__ import annotations

from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.av_scenes.const import DOMAIN
from custom_components.av_scenes.coordinator import AVScenesCoordinator

ONKYO = "media_player.onkyo_receiver"
BEAMER = "media_player.epson_ehtw7400"
VU = "media_player.vu_as2b_de"
PLUG_BEAMER = "switch.wz_steckdose_beamer_5_3_schwarz"
PLUG_MM = "switch.wz_steckdose_multimedia_5_4_grau"
KITCHEN = "media_player.kueche"


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
        # Fake clock, advanced by the fake sleep
        self.clock = 0.0
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

    async def fake_sleep(self, seconds: float) -> None:
        """Advance the fake clock instead of waiting."""
        self.sleeps.append(seconds)
        self.clock += seconds

    def names(self) -> list[tuple[str, tuple[str, ...]]]:
        return [(name, entities) for name, entities, _ in self.calls]


async def setup(hass: HomeAssistant, devices: Devices, data: dict[str, Any]) -> AVScenesCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=1, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator: AVScenesCoordinator = hass.data[DOMAIN][entry.entry_id]

    coordinator._async_sleep = devices.fake_sleep  # type: ignore[method-assign]
    coordinator._now = lambda: devices.clock  # type: ignore[method-assign]
    coordinator._async_call = devices.engine_call  # type: ignore[method-assign]
    return coordinator
