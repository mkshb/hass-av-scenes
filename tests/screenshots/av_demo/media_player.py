"""Receiver, projector, set-top box and Apple TV."""
from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature as F,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import DOMAIN, POSTER

POWER = F.TURN_ON | F.TURN_OFF
VOLUME = F.VOLUME_SET | F.VOLUME_STEP | F.VOLUME_MUTE
PLAYBACK = F.PLAY | F.PAUSE | F.STOP | F.NEXT_TRACK | F.PREVIOUS_TRACK

CHANNELS = [
    ("Channel One", "The Evening News", "World and weather"),
    ("Channel Two", "Northern Lights", "Documentary"),
    ("Channel Three", "Kitchen Stories", "Cooking show"),
]

APPS = ["Netflix", "Disney+", "Prime Video", "YouTube", "Plex", "Apple TV"]


async def async_setup_platform(
    hass: HomeAssistant, config: Any, add_entities: AddEntitiesCallback, discovery_info: Any = None
) -> None:
    add_entities(
        [
            Player(
                "av_receiver",
                "AV receiver",
                outlet="av_rack",
                boot=3,
                features=POWER | VOLUME | F.SELECT_SOURCE | F.SELECT_SOUND_MODE,
                sources=["SAT", "Apple TV", "Blu-ray", "NET", "TV", "PHONO"],
                sound_modes=["Dolby Atmos", "DTS:X", "THX Cinema", "Stereo", "Direct"],
            ),
            Player(
                "projector",
                "Projector",
                outlet="projector",
                boot=5,
                features=POWER | F.SELECT_SOURCE,
                sources=["HDMI1", "HDMI2"],
            ),
            SetTopBox(),
            AppleTV(),
        ]
    )


class Player(MediaPlayerEntity):
    _attr_should_poll = False
    _attr_volume_step = 0.02

    def __init__(
        self,
        key: str,
        name: str,
        *,
        outlet: str | None = None,
        boot: float = 0,
        features: F = POWER,
        sources: list[str] | None = None,
        sound_modes: list[str] | None = None,
    ) -> None:
        self._outlet = outlet
        self._boot = boot
        self._booted = outlet is None
        self._cancel_boot: Any = None
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_supported_features = features
        self._attr_source_list = sources
        self._attr_sound_mode_list = sound_modes
        self._attr_source = sources[0] if sources else None
        self._attr_sound_mode = sound_modes[0] if sound_modes else None
        self._attr_volume_level = 0.3
        self._attr_is_volume_muted = False
        self._attr_state = MediaPlayerState.OFF

    async def async_added_to_hass(self) -> None:
        if self._outlet:
            self.hass.data[DOMAIN].listen(self._outlet, self._power_changed)

    @callback
    def _power_changed(self, on: bool) -> None:
        if self._cancel_boot:
            self._cancel_boot.cancel()
            self._cancel_boot = None
        if on:
            self._cancel_boot = self.hass.loop.call_later(self._boot, self._booted_up)
        else:
            self._booted = False
            self._attr_state = MediaPlayerState.OFF
            self.async_write_ha_state()

    @callback
    def _booted_up(self) -> None:
        self._cancel_boot = None
        self._booted = True
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._booted

    def _on_state(self) -> MediaPlayerState:
        return MediaPlayerState.ON

    async def async_turn_on(self) -> None:
        self._attr_state = self._on_state()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        self._attr_source = source
        self.async_write_ha_state()

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        self._attr_sound_mode = sound_mode
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        self._attr_volume_level = round(volume, 2)
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()


class SetTopBox(Player):
    """Satellite receiver; next and previous track change the channel."""

    def __init__(self) -> None:
        super().__init__(
            "satellite_receiver",
            "Satellite receiver",
            outlet="av_rack",
            boot=4,
            features=POWER | PLAYBACK,
        )
        self._channel = 0
        self._attr_media_content_type = MediaType.CHANNEL

    def _on_state(self) -> MediaPlayerState:
        return MediaPlayerState.PLAYING

    @property
    def media_title(self) -> str | None:
        return CHANNELS[self._channel][1]

    @property
    def media_artist(self) -> str | None:
        return CHANNELS[self._channel][2]

    @property
    def media_channel(self) -> str | None:
        return CHANNELS[self._channel][0]

    @property
    def app_name(self) -> str | None:
        return CHANNELS[self._channel][0]

    async def async_media_next_track(self) -> None:
        self._channel = (self._channel + 1) % len(CHANNELS)
        self.async_write_ha_state()

    async def async_media_previous_track(self) -> None:
        self._channel = (self._channel - 1) % len(CHANNELS)
        self.async_write_ha_state()


class AppleTV(Player):
    """Always powered; its apps are its sources."""

    def __init__(self) -> None:
        super().__init__(
            "apple_tv",
            "Apple TV",
            features=POWER | PLAYBACK | F.SELECT_SOURCE | F.SEEK,
            sources=APPS,
        )
        self._attr_source = "Netflix"
        self._attr_media_content_type = MediaType.MOVIE
        self._attr_media_duration = 7260
        self._attr_media_image_remotely_accessible = True

    def _on_state(self) -> MediaPlayerState:
        self._attr_media_position = 2710
        self._attr_media_position_updated_at = dt_util.utcnow()
        return MediaPlayerState.PLAYING

    @property
    def app_name(self) -> str | None:
        return self.source if self.state != MediaPlayerState.OFF else None

    @property
    def media_title(self) -> str | None:
        return "The Quiet Horizon" if self.state != MediaPlayerState.OFF else None

    @property
    def entity_picture(self) -> str | None:
        return POSTER if self.state != MediaPlayerState.OFF else None

    async def async_media_pause(self) -> None:
        self._attr_media_position = self.media_position + (
            dt_util.utcnow() - self._attr_media_position_updated_at
        ).total_seconds()
        self._attr_media_position_updated_at = dt_util.utcnow()
        await super().async_media_pause()
