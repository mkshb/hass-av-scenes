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

from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import State

from .const import (
    COMMAND_GROUPS,
    CONF_COMMANDS,
    CONF_DEVICES,
    CONF_ENTITY_ID,
    CONF_REMOTE,
    CONF_REMOTE_ENTITY,
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
        # The service schema reads numbers as float: "1" arrives as 1.0
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        data["source"] = str(value)
    return "media_player", service, data
