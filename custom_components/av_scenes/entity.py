"""Shared entity base class for the AV Scenes integration."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_NAME_PREFIX
from .coordinator import AVScenesCoordinator


def room_device_info(room_id: str, room_name: str) -> DeviceInfo:
    """Return the shared device info for a room's virtual HA device.

    All entities of a room must return identical ``DeviceInfo`` so they group
    under one device. ``suggested_area`` links it to the matching HA Area.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, room_id)},
        name=f"{DEVICE_NAME_PREFIX}: {room_name}",
        manufacturer="AV Scenes",
        model="Activity Controller",
        suggested_area=room_name,
    )


class AVRoomEntity(CoordinatorEntity[AVScenesCoordinator]):
    """Base entity for all per-room AV Scenes entities.

    Provides the common device grouping (one virtual HA device per room,
    linked to the matching HA Area) and caches the room's display name.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: AVScenesCoordinator, room_id: str) -> None:
        """Initialize the room entity."""
        super().__init__(coordinator)
        self.room_id = room_id
        self._room_name: str = coordinator.rooms[room_id].get("name", room_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the shared device info. ``suggested_area`` links to the HA Area."""
        return room_device_info(self.room_id, self._room_name)
