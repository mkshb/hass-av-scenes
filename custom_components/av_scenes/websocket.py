"""Websocket API for the remote control card and the configuration panel.

control/*: what the card shows. Commands go through the regular services
(``av_scenes.start_activity``, ``send_command`` …).

config/*: read, check and save the configuration (admins only), the
remembered source lists of the media players for the pickers, the flow of
an activity (what a start or stop switches, see flow.py) and a preview of
the card while an activity runs. Saving
takes the revision that was read, so changes made elsewhere in the meantime
(options flow, a second browser) are not overwritten silently.
"""
from __future__ import annotations

import hashlib
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.json import json_bytes_sorted

from .const import (
    ATTR_ACTIVITY,
    ATTR_ROOM,
    CONF_ACTIVITIES,
    CONF_AREA_ID,
    CONF_DEFAULT_ACTIVITY,
    CONF_NAME,
    CONF_ROOMS,
    DOMAIN,
    SIGNAL_ROOMS_UPDATED,
)
from .control import activity_list, describe_command, remote_view, route_summary
from .coordinator import AVScenesCoordinator
from .flow import plan_start, plan_stop
from .model import async_validate_config, find_missing_entities


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
    websocket_api.async_register_command(hass, ws_config_get)
    websocket_api.async_register_command(hass, ws_config_validate)
    websocket_api.async_register_command(hass, ws_config_save)
    websocket_api.async_register_command(hass, ws_config_sources)
    websocket_api.async_register_command(hass, ws_config_flow)
    websocket_api.async_register_command(hass, ws_config_remote)


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


# ----------------------------------------------------------------------
# Configuration (admins only)
# ----------------------------------------------------------------------


def revision(rooms: dict[str, Any]) -> str:
    """Fingerprint of a configuration, independent of key order."""
    return hashlib.sha256(json_bytes_sorted(rooms)).hexdigest()[:16]


def _entry(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> ConfigEntry | None:
    """The entry to configure: the given one, or the only one there is.

    Works on the config entry, not the coordinator, so a configuration that
    fails to load can still be fixed.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if entry_id := msg.get("entry_id"):
        entries = [e for e in entries if e.entry_id == entry_id]
    if len(entries) != 1:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "No AV Scenes entry found" if not entries else "Several entries, pass entry_id",
        )
        return None
    return entries[0]


async def _async_check(
    hass: HomeAssistant, rooms: Any, room_id: str | None
) -> dict[str, Any]:
    """Validate rooms; errors block saving, missing entities are warnings."""
    if not isinstance(rooms, dict):
        return {"error": {"path": [], "message": "rooms must be a mapping"}, "missing": []}
    try:
        await async_validate_config(hass, {CONF_ROOMS: rooms})
    except vol.Invalid as err:
        return {
            "error": {"path": [str(p) for p in err.path], "message": err.msg},
            "missing": [],
        }
    missing = [
        {"room": ref.room_id, "path": ref.path, "entity_id": ref.entity_id}
        for ref in find_missing_entities(hass, {CONF_ROOMS: rooms})
        if room_id is None or ref.room_id == room_id
    ]
    return {"error": None, "missing": missing}


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/config/get", vol.Optional("entry_id"): str}
)
@websocket_api.require_admin
@callback
def ws_config_get(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The stored configuration with its revision."""
    if (entry := _entry(hass, connection, msg)) is None:
        return
    rooms = dict(entry.data.get(CONF_ROOMS) or {})
    connection.send_result(
        msg["id"],
        {"entry_id": entry.entry_id, "rooms": rooms, "revision": revision(rooms)},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/config/validate",
        vol.Required(CONF_ROOMS): dict,
        vol.Optional(ATTR_ROOM): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_config_validate(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Check a configuration without saving it.

    With ``room``, only that room's unknown entities are reported.
    """
    connection.send_result(
        msg["id"], await _async_check(hass, msg[CONF_ROOMS], msg.get(ATTR_ROOM))
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/config/save",
        vol.Required(CONF_ROOMS): dict,
        vol.Required("revision"): str,
        vol.Optional("entry_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_config_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Save a configuration that was read with the given revision."""
    if (entry := _entry(hass, connection, msg)) is None:
        return
    current = dict(entry.data.get(CONF_ROOMS) or {})
    if revision(current) != msg["revision"]:
        connection.send_error(
            msg["id"],
            "conflict",
            "The configuration was changed elsewhere; reload it before saving",
        )
        return
    rooms = msg[CONF_ROOMS]
    check = await _async_check(hass, rooms, None)
    if check["error"] is not None:
        error = check["error"]
        connection.send_error(
            msg["id"],
            "invalid_config",
            f"{'.'.join(error['path'])}: {error['message']}" if error["path"] else error["message"],
        )
        return
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_ROOMS: rooms})
    connection.send_result(
        msg["id"], {"revision": revision(rooms), "missing": check["missing"]}
    )


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/config/sources"})
@websocket_api.require_admin
@callback
def ws_config_sources(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Last known source list per media player, also while it is off."""
    sources: dict[str, list[str]] = {}
    for coordinator in _coordinators(hass):
        sources.update(coordinator.source_lists)
    connection.send_result(msg["id"], sources)


_UNKNOWN_ACTIVITY = {"error": {"path": [], "message": "Unknown activity"}}


async def _async_edited_room(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any] | None:
    """The room being edited (``config``), validated, with its activity.

    Sends the validation error, or an unknown activity, as the result and
    returns None then.
    """
    room_id: str = msg[ATTR_ROOM]
    try:
        config = await async_validate_config(hass, {CONF_ROOMS: {room_id: msg["config"]}})
    except vol.Invalid as err:
        error = {"path": [str(p) for p in err.path], "message": err.msg}
        connection.send_result(msg["id"], {"error": error})
        return None
    room = config[CONF_ROOMS][room_id]
    if msg[ATTR_ACTIVITY] not in room[CONF_ACTIVITIES]:
        connection.send_result(msg["id"], _UNKNOWN_ACTIVITY)
        return None
    return room


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/config/flow",
        vol.Required(ATTR_ROOM): str,
        vol.Required("config"): dict,
        vol.Required(ATTR_ACTIVITY): str,
        vol.Optional("mode", default="start"): vol.In(["start", "stop"]),
        vol.Optional("from"): vol.Any(None, str),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_config_flow(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """What a start or stop of an activity switches, when and how.

    Works on the room as it is being edited (``config``), saved or not. A
    configuration that does not validate yields its error instead.
    """
    if (room := await _async_edited_room(hass, connection, msg)) is None:
        return
    room_id: str = msg[ATTR_ROOM]
    activity: str = msg[ATTR_ACTIVITY]
    previous: str | None = msg.get("from")
    if previous is not None and previous not in room[CONF_ACTIVITIES]:
        connection.send_result(msg["id"], _UNKNOWN_ACTIVITY)
        return
    # Other rooms as saved, for outlets they share with this one
    others: dict[str, Any] = {}
    for coordinator in _coordinators(hass):
        others.update(coordinator.rooms)
    if msg["mode"] == "stop":
        flow = plan_stop(hass, room_id, room, activity, others)
    else:
        flow = plan_start(hass, room_id, room, activity, previous, others)
    connection.send_result(msg["id"], {"error": None, **flow})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/config/remote",
        vol.Required(ATTR_ROOM): str,
        vol.Required("config"): dict,
        vol.Required(ATTR_ACTIVITY): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_config_remote(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The card as it looks while an activity runs, and where each button goes.

    Works on the room as it is being edited (``config``), saved or not.
    ``view`` has the shape of control/subscribe; ``targets`` describes each
    button by "command|device" (device empty when it is routed).
    """
    if (room := await _async_edited_room(hass, connection, msg)) is None:
        return
    room_id: str = msg[ATTR_ROOM]
    activity_id: str = msg[ATTR_ACTIVITY]
    activity = room[CONF_ACTIVITIES][activity_id]
    remote = remote_view(room, activity)
    registry = er.async_get(hass)

    def platform_of(entity_id: str) -> str | None:
        entry = registry.async_get(entity_id)
        return entry.platform if entry is not None else None

    buttons = [(c, None) for group in remote["groups"].values() for c in group["commands"]]
    buttons += [(button["command"], button["device"]) for button in remote["buttons"]]
    targets = {
        f"{command}|{device_id or ''}": describe_command(
            room, activity, command, device_id, platform_of
        )
        for command, device_id in buttons
    }
    view = {
        "entry_id": "",
        "room": room_id,
        "name": room.get(CONF_NAME, room_id),
        "area_id": room.get(CONF_AREA_ID),
        "state": "active",
        "activity": activity_id,
        "error": None,
        "warnings": [],
        "progress": [0, 0],
        "default_activity": room.get(CONF_DEFAULT_ACTIVITY),
        "activities": activity_list(room),
        "remote": remote,
    }
    connection.send_result(
        msg["id"],
        {"error": None, "view": view, "targets": targets, "routes": route_summary(room, activity)},
    )
