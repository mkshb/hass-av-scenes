"""Fake living room devices for the README screenshots.

Power outlets supply the receiver, the set-top box and the projector: while
an outlet is off, its devices are unavailable, and after it comes on they
become available once their boot time has passed, like real devices whose
integration reconnects.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

DOMAIN = "av_demo"
POSTER = "/av_demo/poster.svg"

PLATFORMS = (Platform.SWITCH, Platform.MEDIA_PLAYER, Platform.REMOTE, Platform.LIGHT, Platform.COVER)


class Outlets:
    """State of the outlets and the devices listening to them."""

    def __init__(self) -> None:
        self.on: dict[str, bool] = {"av_rack": False, "projector": False}
        self._listeners: dict[str, list[Callable[[bool], None]]] = {}

    def listen(self, outlet: str, listener: Callable[[bool], None]) -> None:
        self._listeners.setdefault(outlet, []).append(listener)

    @callback
    def set(self, outlet: str, on: bool) -> None:
        self.on[outlet] = on
        for listener in self._listeners.get(outlet, []):
            listener(on)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the fake devices."""
    hass.data[DOMAIN] = Outlets()
    await hass.http.async_register_static_paths(
        [StaticPathConfig(POSTER, str(Path(__file__).parent / "poster.svg"), True)]
    )
    for platform in PLATFORMS:
        hass.async_create_task(async_load_platform(hass, platform, DOMAIN, {}, config))
    return True
