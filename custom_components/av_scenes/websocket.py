"""Websocket API for the remote control card.

Commands go through the regular services (``av_scenes.start_activity``,
``send_command`` …); the websocket only delivers what the card shows.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import ATTR_ROOM, DOMAIN, SIGNAL_ROOMS_UPDATED
from .coordinator import AVScenesCoordinator


def _coordinators(hass: HomeAssistant) -> list[AVScenesCoordinator]:
    return [
        c for c in hass.data.get(DOMAIN, {}).values() if isinstance(c, AVScenesCoordinator)
    ]


def find_room(
    hass: HomeAssistant, room_id: str, entry_id: str | None = None
) -> AVScenesCoordinator | None:
    """Return the coordinator that manages a room."""
    for coordinator in _coordinators(hass):
        if entry_id is not None and coordinator.entry.entry_id != entry_id:
            continue
        if room_id in coordinator.rooms:
            return coordinator
    return None


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the websocket commands."""
    websocket_api.async_register_command(hass, ws_rooms)
    websocket_api.async_register_command(hass, ws_subscribe)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/control/rooms"})
@callback
def ws_rooms(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """List all rooms (for the card editor)."""
    connection.send_result(
        msg["id"],
        [
            {
                "entry_id": coordinator.entry.entry_id,
                "room": room_id,
                "name": room.get("name", room_id),
                "area_id": room.get("area_id"),
            }
            for coordinator in _coordinators(hass)
            for room_id, room in coordinator.rooms.items()
        ],
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/control/subscribe",
        vol.Required(ATTR_ROOM): str,
        vol.Optional("entry_id"): str,
    }
)
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send the view of a room now and whenever it changes.

    The room survives a reload of its entry; while it is gone (entry
    unloaded, room deleted) ``null`` is sent.
    """
    room_id: str = msg[ATTR_ROOM]
    entry_id: str | None = msg.get("entry_id")
    last: list[Any] = [object()]

    @callback
    def _send() -> None:
        coordinator = find_room(hass, room_id, entry_id)
        view = coordinator.room_view(room_id) if coordinator is not None else None
        if view != last[0]:
            last[0] = view
            connection.send_message(websocket_api.event_message(msg["id"], view))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, SIGNAL_ROOMS_UPDATED, _send
    )
    connection.send_result(msg["id"])
    _send()
