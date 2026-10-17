"""Remote control: route buttons of the running activity to its devices.

An activity routes each command group (volume, channels, transport,
navigation) to one of its devices. A command then runs

1. the activity's own ``commands`` entry, if there is one,
2. else on the device its group is routed to: the device's ``commands``
   entry, its ``remote_entity`` for navigation keys, or the built-in
   media_player action,
3. else the ``commands`` entry of the first device of the activity that
   defines it (e.g. digit keys only the receiver box knows).

Without explicit routing, volume goes to the first media player of the
activity and transport to the last one. Channels go to the last media player
only when it is a separate source (a TV box behind the receiver); a receiver
alone would get its track keys twice. Navigation goes to the last device that
defines navigation commands.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import State

from .const import (
    COMMAND_GROUPS,
    CONF_ACTIVITIES,
    CONF_BUTTONS,
    CONF_COMMAND,
    CONF_COMMANDS,
    CONF_DEVICE,
    CONF_DEVICES,
    CONF_ENTITY_ID,
    CONF_ICON,
    CONF_NAME,
    CONF_READY,
    CONF_REMOTE,
    CONF_REMOTE_ENTITY,
    CONF_SOURCE,
    GROUP_CHANNELS,
    GROUP_NAVIGATION,
    GROUP_TRANSPORT,
    GROUP_VOLUME,
)

# Quick-select buttons send this with the source (or app) as value
COMMAND_SELECT_SOURCE = "select_source"

# Built-in actions of a media player: command -> service
_MEDIA_PLAYER_SERVICES: dict[str, str] = {
    "volume_up": "volume_up",
    "volume_down": "volume_down",
    "mute": "volume_mute",
    "volume_set": "volume_set",
    # Set-top boxes (e.g. enigma2) map next/previous track to the channel keys
    "channel_up": "media_next_track",
    "channel_down": "media_previous_track",
    "play_pause": "media_play_pause",
    "play": "media_play",
    "pause": "media_pause",
    "stop": "media_stop",
    "next": "media_next_track",
    "previous": "media_previous_track",
    COMMAND_SELECT_SOURCE: "select_source",
}

# Navigation keys a remote entity handles: command -> remote command, per
# integration of the remote; others get the command name unchanged
REMOTE_KEYS: tuple[str, ...] = ("up", "down", "left", "right", "ok", "back", "home", "menu")
_REMOTE_KEY_NAMES: dict[str, dict[str, str]] = {
    # Apple TV: the menu button goes back; top_menu is the app's main menu
    "apple_tv": {"ok": "select", "back": "menu", "menu": "top_menu"},
    "androidtv_remote": {
        "up": "DPAD_UP",
        "down": "DPAD_DOWN",
        "left": "DPAD_LEFT",
        "right": "DPAD_RIGHT",
        "ok": "DPAD_CENTER",
        "back": "BACK",
        "home": "HOME",
        "menu": "MENU",
    },
}


def remote_call(
    command: str, remote: str, platform: str | None
) -> tuple[str, str, dict[str, Any]] | None:
    """remote.send_command for a navigation key, or None for other commands."""
    if command not in REMOTE_KEYS:
        return None
    name = _REMOTE_KEY_NAMES.get(platform or "", {}).get(command, command)
    return "remote", "send_command", {ATTR_ENTITY_ID: remote, "command": name}


_COMMAND_TO_GROUP: dict[str, str] = {
    command: group for group, commands in COMMAND_GROUPS.items() for command in commands
}


def command_group(command: str) -> str | None:
    """Return the group a standard command belongs to."""
    return _COMMAND_TO_GROUP.get(command)


def _is_media_player(device: dict[str, Any]) -> bool:
    return device[CONF_ENTITY_ID].startswith("media_player.")


def routing(room: dict[str, Any], activity: dict[str, Any]) -> dict[str, str | None]:
    """Device per command group for an activity (explicit or default)."""
    devices: dict[str, Any] = room[CONF_DEVICES]
    ids: list[str] = activity[CONF_DEVICES]
    players = [d for d in ids if _is_media_player(devices[d])]
    navigators = [
        d
        for d in ids
        if devices[d].get(CONF_REMOTE_ENTITY)
        or any(c in devices[d][CONF_COMMANDS] for c in COMMAND_GROUPS[GROUP_NAVIGATION])
    ]
    defaults: dict[str, str | None] = {
        GROUP_VOLUME: players[0] if players else None,
        GROUP_CHANNELS: players[-1] if len(players) > 1 else None,
        GROUP_TRANSPORT: players[-1] if players else None,
        GROUP_NAVIGATION: navigators[-1] if navigators else None,
    }
    remote = activity.get(CONF_REMOTE) or {}
    return {group: remote.get(group, defaults[group]) for group in COMMAND_GROUPS}


def device_commands(device: dict[str, Any]) -> list[str]:
    """Commands a device can run: its own plus the built-in ones."""
    commands = list(device[CONF_COMMANDS])
    if device.get(CONF_REMOTE_ENTITY):
        commands += [c for c in REMOTE_KEYS if c not in commands]
    if _is_media_player(device):
        commands += [c for c in _MEDIA_PLAYER_SERVICES if c not in commands]
    return commands


def builtin_call(
    command: str, entity_id: str, state: State | None, value: Any = None
) -> tuple[str, str, dict[str, Any]] | None:
    """Service call for a built-in command, or None if there is none."""
    if not entity_id.startswith("media_player."):
        return None
    service = _MEDIA_PLAYER_SERVICES.get(command)
    if service is None:
        return None
    data: dict[str, Any] = {ATTR_ENTITY_ID: entity_id}
    if command == "mute":
        muted = bool(state and state.attributes.get("is_volume_muted"))
        data["is_volume_muted"] = not muted
    elif command == "volume_set":
        if value is None:
            raise ValueError("volume_set needs a value between 0 and 1")
        data["volume_level"] = max(0.0, min(1.0, float(value)))
    elif command == COMMAND_SELECT_SOURCE:
        if value is None or value == "":
            raise ValueError("select_source needs the source as value")
        # A number written in YAML: 1.0 selects source "1"
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        data["source"] = str(value)
    return "media_player", service, data


def route(room: dict[str, Any], activity: dict[str, Any], command: str) -> str | None:
    """The device a command of the running activity goes to, or None.

    The activity's own ``commands`` are checked before, by the caller.
    """
    group = command_group(command)
    if group is not None:
        return routing(room, activity)[group]
    devices: dict[str, Any] = room[CONF_DEVICES]
    return next(
        (d for d in activity[CONF_DEVICES] if command in devices[d][CONF_COMMANDS]), None
    )


def button_view(button: dict[str, Any]) -> dict[str, Any]:
    """A remote button as the card shows and sends it."""
    if CONF_SOURCE in button:
        # Quick select: select_source with the source as value
        return {
            "command": COMMAND_SELECT_SOURCE,
            "value": button[CONF_SOURCE],
            "name": button.get(CONF_NAME) or button[CONF_SOURCE],
            "icon": button.get(CONF_ICON),
            "device": button[CONF_DEVICE],
        }
    return {
        "command": button[CONF_COMMAND],
        "value": None,
        "name": button.get(CONF_NAME),
        "icon": button.get(CONF_ICON),
        "device": button.get(CONF_DEVICE),
    }


def remote_view(room: dict[str, Any], activity: dict[str, Any]) -> dict[str, Any]:
    """The remote control the card shows while an activity runs."""
    devices = room[CONF_DEVICES]
    own: list[str] = list(activity[CONF_COMMANDS])
    groups: dict[str, Any] = {}
    for group, device_id in routing(room, activity).items():
        available = set(own)
        if device_id is not None:
            available.update(device_commands(devices[device_id]))
        commands = [c for c in COMMAND_GROUPS[group] if c in available]
        if commands:
            groups[group] = {
                "device": device_id,
                "entity_id": devices[device_id][CONF_ENTITY_ID] if device_id else None,
                "commands": commands,
            }
    return {
        "groups": groups,
        "buttons": [button_view(button) for button in activity[CONF_REMOTE][CONF_BUTTONS]],
    }


def route_summary(room: dict[str, Any], activity: dict[str, Any]) -> list[dict[str, Any]]:
    """Per button group: the device it goes to, whether that was chosen or
    automatic, and the buttons it gets (none: the group is not shown)."""
    view = remote_view(room, activity)["groups"]
    remote = activity.get(CONF_REMOTE) or {}
    return [
        {
            "group": group,
            "device": device_id,
            "mode": ("hidden" if device_id is None else "set") if group in remote else "auto",
            "commands": view[group]["commands"] if group in view else [],
        }
        for group, device_id in routing(room, activity).items()
    ]


def action_names(actions: Any) -> list[str]:
    """The actions a list of Home Assistant actions calls, also nested ones
    (if/then, choose, parallel and the like)."""
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            action = value.get("action") or value.get("service")
            if isinstance(action, str) and action not in found:
                found.append(action)
            for item in value.values():
                if isinstance(item, (list, dict)):
                    walk(item)

    walk(actions)
    return found


def describe_command(
    room: dict[str, Any],
    activity: dict[str, Any],
    command: str,
    device_id: str | None = None,
    platform_of: Callable[[str], str | None] = lambda entity_id: None,
) -> dict[str, Any]:
    """Where a button of the running activity goes and what runs there.

    Follows AVScenesCoordinator.async_send_command. ``platform_of`` gives
    the integration of a remote entity, for its key names.
    ``via`` is ``activity_commands``, ``device_commands``, ``remote``,
    ``media_player`` or None (the button does nothing).
    """
    devices: dict[str, Any] = room[CONF_DEVICES]
    if device_id is None:
        if command in activity[CONF_COMMANDS]:
            return {
                "via": "activity_commands",
                "device": None,
                "actions": action_names(activity[CONF_COMMANDS][command]),
            }
        device_id = route(room, activity, command)
        if device_id is None:
            return {"via": None, "device": None}
    device = devices[device_id]
    entity_id = device[CONF_ENTITY_ID]
    base = {"device": device_id, "entity_id": entity_id, "ready": bool(device.get(CONF_READY))}
    if command in device[CONF_COMMANDS]:
        return {**base, "via": "device_commands", "actions": action_names(device[CONF_COMMANDS][command])}
    remote = device.get(CONF_REMOTE_ENTITY)
    if remote and (call := remote_call(command, remote, platform_of(remote))):
        return {
            **base,
            "via": "remote",
            "action": "remote.send_command",
            "entity_id": remote,
            "key": call[2]["command"],
        }
    if entity_id.startswith("media_player.") and command in _MEDIA_PLAYER_SERVICES:
        return {**base, "via": "media_player", "action": f"media_player.{_MEDIA_PLAYER_SERVICES[command]}"}
    return {**base, "via": None}


def activity_list(room: dict[str, Any]) -> list[dict[str, Any]]:
    """The activities of a room as the card lists them."""
    return [
        {"id": activity_id, "name": data.get(CONF_NAME, activity_id), "icon": data.get(CONF_ICON)}
        for activity_id, data in room[CONF_ACTIVITIES].items()
    ]
