"""Activity engine for the AV Scenes integration.

Starting an activity
    1. Smart switching: devices of the previous activity that the new one does
       not use are switched off. Their power switches are cut in the
       background once every device on them had its ``delay_after_off``.
    2. Power: all power switches the new activity needs are switched on at
       once so the devices boot in parallel.
    3. ``on_start`` actions start running alongside.
    4. Per device, in order: boot time ``delay_after_power`` (only when its
       power switch was off, counted from switching it on), readiness check
       (``ready``; after its power came on, its integration is reloaded
       first with ``reload_integration``, since it last saw the device
       without power), turn on (only when it is off), ``delay_after_on``
       (only when it was switched on).
    5. Steps.
    6. Wait for ``on_start``; the activity is ``active``.

    A readiness check or ``wait_available`` step with ``on_timeout: abort``
    stops the start; the room goes to ``error`` and never to ``active``.
    So does an unexpected failure while starting or stopping.

Stopping an activity
    ``on_stop`` actions run alongside; devices are switched off in reverse
    order. The room is idle once they are off. Power switches are cut
    afterwards: at once when none of their devices needs a cool-down,
    otherwise in the background after the longest ``delay_after_off`` of
    their devices. A new start keeps the switches it needs, and a switch
    stays on while a running activity of another room needs it.

A new command for a room cancels whatever runs there (a stop during a long
start, a different activity while starting).

Remote buttons (``send_command``) are routed to the devices of the running
activity, see control.py. They do not interfere with starting or stopping.

The source lists of the media players are remembered, so the configuration
panel can offer them while a device is off (an Apple TV lists its apps only
while it is connected).
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import contextlib
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import (
    ConfigEntryError,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.script import SCRIPT_MODE_PARALLEL, Script
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ACTIVITY_STATE_ACTIVE,
    ACTIVITY_STATE_ERROR,
    ACTIVITY_STATE_IDLE,
    ACTIVITY_STATE_STARTING,
    ACTIVITY_STATE_STOPPING,
    CONF_ACTION,
    CONF_ACTIVITIES,
    CONF_AREA_ID,
    CONF_BRIGHTNESS_PCT,
    CONF_COLOR_TEMP_KELVIN,
    CONF_COMMANDS,
    CONF_DEFAULT_ACTIVITY,
    CONF_DATA,
    CONF_DELAY_AFTER_OFF,
    CONF_DELAY_AFTER_ON,
    CONF_DELAY_AFTER_POWER,
    CONF_DEVICE,
    CONF_DEVICES,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_ON_START,
    CONF_ON_STOP,
    CONF_ON_TIMEOUT,
    CONF_POSITION,
    CONF_POWER_SWITCH,
    CONF_READY,
    CONF_RELOAD_INTEGRATION,
    CONF_REMOTE_ENTITY,
    CONF_ROOMS,
    CONF_SOUND_MODE,
    CONF_SOURCE,
    CONF_STATE,
    CONF_STEPS,
    CONF_TARGET,
    CONF_TILT_POSITION,
    CONF_TIMEOUT,
    CONF_TRANSITION,
    CONF_TYPE,
    CONF_VOLUME_LEVEL,
    DEFAULT_SERVICE_TIMEOUT,
    DEVICE_NAME_PREFIX,
    DOMAIN,
    ON_TIMEOUT_ABORT,
    SIGNAL_ROOMS_UPDATED,
    STEP_TYPE_CALL_ACTION,
    STEP_TYPE_DELAY,
    STEP_TYPE_POWER_OFF,
    STEP_TYPE_POWER_ON,
    STEP_TYPE_SET_BRIGHTNESS,
    STEP_TYPE_SET_COLOR_TEMP,
    STEP_TYPE_SET_POSITION,
    STEP_TYPE_SET_SOUND_MODE,
    STEP_TYPE_SET_SOURCE,
    STEP_TYPE_SET_TILT,
    STEP_TYPE_SET_VOLUME,
    STEP_TYPE_WAIT_AVAILABLE,
)
from .control import activity_list, builtin_call, remote_call, remote_view, route
from .model import CONF_DELAY_AFTER, async_validate_config, find_missing_entities

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

# While waiting for a device, an integration still in setup_retry is reloaded
# again after this many seconds instead of waiting for its growing back-off
# (5, 10, 20, 40 s ...), which can miss a device that came up meanwhile
RELOAD_RETRY_INTERVAL = 5.0

# States in which a device counts as switched off
_OFF_STATES = {STATE_OFF, STATE_STANDBY, STATE_UNAVAILABLE, STATE_UNKNOWN, "closed"}

# Persisted states and what they mean after a restart
_RESTORED_STATES = {
    ACTIVITY_STATE_ACTIVE: ACTIVITY_STATE_ACTIVE,
    ACTIVITY_STATE_ERROR: ACTIVITY_STATE_ERROR,
    ACTIVITY_STATE_STARTING: ACTIVITY_STATE_ERROR,
    ACTIVITY_STATE_STOPPING: ACTIVITY_STATE_ERROR,
}


# Run state of the room whose command runs in the current task (and the hook
# tasks it spawns), so warnings end up at the right room.
_current_room: ContextVar["RoomRuntime | None"] = ContextVar("av_scenes_room", default=None)


def power_service(entity_id: str, *, on: bool) -> tuple[str, str]:
    """The action that switches a device on or off: covers open and close."""
    if entity_id.startswith("cover."):
        return "cover", "open_cover" if on else "close_cover"
    return "homeassistant", SERVICE_TURN_ON if on else SERVICE_TURN_OFF


def can_switch(hass: HomeAssistant, entity_id: str, *, on: bool) -> bool:
    """False for a media player that cannot be switched, e.g. a Sonos speaker.

    Without a known state (unavailable) the call is tried anyway.
    """
    if not entity_id.startswith("media_player."):
        return True
    state = hass.states.get(entity_id)
    if state is None or "supported_features" not in state.attributes:
        return True
    feature = MediaPlayerEntityFeature.TURN_ON if on else MediaPlayerEntityFeature.TURN_OFF
    return bool(state.attributes["supported_features"] & feature)


def power_switches(devices: dict[str, Any], device_ids: list[str]) -> list[str]:
    """Power switches of the given devices, in order, without duplicates."""
    switches: list[str] = []
    for device_id in device_ids:
        switch = devices[device_id].get(CONF_POWER_SWITCH)
        if switch and switch not in switches:
            switches.append(switch)
    return switches


def step_service(
    step_type: str, step: dict[str, Any], entity_id: str | None
) -> tuple[str, str, dict[str, Any], dict[str, Any] | None] | None:
    """The action a settings step runs: domain, service, data and target."""
    target = {ATTR_ENTITY_ID: entity_id}
    if step_type == STEP_TYPE_SET_SOURCE:
        return "media_player", "select_source", {"source": step[CONF_SOURCE]}, target
    if step_type == STEP_TYPE_SET_VOLUME:
        return (
            "media_player",
            "volume_set",
            {"volume_level": step[CONF_VOLUME_LEVEL]},
            target,
        )
    if step_type == STEP_TYPE_SET_SOUND_MODE:
        return (
            "media_player",
            "select_sound_mode",
            {"sound_mode": step[CONF_SOUND_MODE]},
            target,
        )
    if step_type in (STEP_TYPE_SET_BRIGHTNESS, STEP_TYPE_SET_COLOR_TEMP):
        data = {
            key: step[key]
            for key in (CONF_BRIGHTNESS_PCT, CONF_COLOR_TEMP_KELVIN, CONF_TRANSITION)
            if key in step
        }
        return "light", SERVICE_TURN_ON, data, target
    if step_type == STEP_TYPE_SET_POSITION:
        return "cover", "set_cover_position", {"position": step[CONF_POSITION]}, target
    if step_type == STEP_TYPE_SET_TILT:
        return (
            "cover",
            "set_cover_tilt_position",
            {"tilt_position": step[CONF_TILT_POSITION]},
            target,
        )
    if step_type == STEP_TYPE_CALL_ACTION:
        domain, service = step[CONF_ACTION].split(".", 1)
        return domain, service, dict(step.get(CONF_DATA) or {}), step.get(CONF_TARGET)
    _LOGGER.warning("Unknown step type: %s", step_type)
    return None


class ActivityAborted(Exception):
    """Raised when a readiness check aborts an activity start."""


@dataclass
class RoomRuntime:
    """Mutable run state of one room."""

    activity: str | None = None
    state: str = ACTIVITY_STATE_IDLE
    progress: tuple[int, int] = (0, 0)
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    last_activity: str | None = None
    task: asyncio.Task | None = None
    command: tuple[str, str | None] | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Counts the commands; one still waiting for the lock is dropped once a
    # newer one arrived
    generation: int = 0
    # power switch -> background task that cuts it after the cool-down
    pending_cuts: dict[str, asyncio.Task] = field(default_factory=dict)
    # power switch -> devices cooling down on it and when it goes off, for the card
    cooling: dict[str, dict[str, Any]] = field(default_factory=dict)
    # What a start or stop is busy with, for the card (see _doing)
    current: dict[str, Any] | None = None


class AVScenesCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Run activities for all rooms of one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
            config_entry=entry,
        )
        self.entry = entry
        self.rooms: dict[str, dict[str, Any]] = {}
        self.service_timeout: float = DEFAULT_SERVICE_TIMEOUT
        self._runtime: dict[str, RoomRuntime] = {}
        # (room, activity, on_start|on_stop) -> hook
        self._scripts: dict[tuple[str, str, str], Script] = {}
        # (room, "device"|"activity", id, command) -> command actions
        self._command_scripts: dict[tuple[str, str, str, str], Script] = {}
        # config entry -> running reload, so repeated checks do not pile up
        self._reloads: dict[str, asyncio.Task] = {}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.state"
        )
        self._restored = False
        # media player -> its last known source list
        self._sources: dict[str, list[str]] = {}
        self._unsub_sources: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------
    # Views used by the entity platforms
    # ------------------------------------------------------------------

    def runtime(self, room_id: str) -> RoomRuntime:
        """Return (and create) the run state of a room."""
        return self._runtime.setdefault(room_id, RoomRuntime())

    @property
    def active_activities(self) -> dict[str, str]:
        """Room -> activity that is running, starting, stopping or failed."""
        return {
            room_id: rt.activity
            for room_id, rt in self._runtime.items()
            if rt.activity is not None
        }

    @property
    def activity_states(self) -> dict[str, str]:
        """Room -> idle / starting / active / stopping / error."""
        return {room_id: rt.state for room_id, rt in self._runtime.items()}

    @property
    def activity_progress(self) -> dict[str, tuple[int, int]]:
        """Room -> (current item, total items)."""
        return {room_id: rt.progress for room_id, rt in self._runtime.items()}

    def activity_name(self, room_id: str, activity_id: str) -> str:
        """Return the display name of an activity."""
        activity = self.rooms.get(room_id, {}).get(CONF_ACTIVITIES, {}).get(activity_id, {})
        return activity.get(CONF_NAME) or activity_id

    @staticmethod
    def entity_layout(rooms: dict[str, Any]) -> list[tuple[str, str, list[tuple[str, str]]]]:
        """What the entities are made of: rooms and activities with their names.

        Sorted, since the order of the stored keys is not stable.
        """
        return sorted(
            (
                room_id,
                room.get(CONF_NAME, room_id),
                sorted(
                    (activity_id, activity.get(CONF_NAME, activity_id))
                    for activity_id, activity in (room.get(CONF_ACTIVITIES) or {}).items()
                ),
            )
            for room_id, room in rooms.items()
        )

    def device_info(self, room_id: str) -> DeviceInfo:
        """The device of a room, which holds its entities.

        It goes into the room's area. Without one, it goes into an area named
        like the room if there is one; no area is created for it.
        """
        room = self.rooms.get(room_id, {})
        name = room.get(CONF_NAME, room_id)
        info = DeviceInfo(
            identifiers={(DOMAIN, room_id)},
            name=f"{DEVICE_NAME_PREFIX}: {name}",
            manufacturer="AV Scenes",
            model="Activity Controller",
        )
        areas = ar.async_get(self.hass)
        area = areas.async_get_area(room.get(CONF_AREA_ID) or "") or areas.async_get_area_by_name(
            name
        )
        if area is not None:
            info["suggested_area"] = area.name
        return info

    @callback
    def async_apply_areas(self) -> None:
        """Move the rooms' devices into the areas the configuration names.

        A suggested area only counts when a device is created; this also
        covers devices that exist already and areas changed later.
        """
        areas = ar.async_get(self.hass)
        devices = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(devices, self.entry.entry_id):
            room_id = next((i for d, i in device.identifiers if d == DOMAIN), None)
            area_id = self.rooms.get(room_id, {}).get(CONF_AREA_ID) if room_id else None
            if area_id and area_id != device.area_id and areas.async_get_area(area_id):
                devices.async_update_device(device.id, area_id=area_id)

    def resolve_activity(self, room_id: str, activity: str) -> str | None:
        """Map an activity id or display name to its id."""
        activities = self.rooms.get(room_id, {}).get(CONF_ACTIVITIES, {})
        if activity in activities:
            return activity
        for activity_id, data in activities.items():
            if data.get(CONF_NAME) == activity:
                return activity_id
        return None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Validate the configuration and prepare the hook scripts."""
        try:
            config = await async_validate_config(self.hass, dict(self.entry.data))
        except vol.Invalid as err:
            path = ".".join(str(p) for p in err.path)
            raise ConfigEntryError(f"Invalid configuration at {path}: {err.msg}") from err

        self.rooms = config[CONF_ROOMS]
        self._build_scripts()
        self._update_issues()

        if not self._restored:
            self._restored = True
            await self._async_restore()
        self._track_sources()

        return config

    def _build_scripts(self) -> None:
        self._scripts = {}
        self._command_scripts = {}

        def script(actions: list[dict[str, Any]], name: str) -> Script:
            return Script(
                self.hass,
                actions,
                f"AV Scenes {name}",
                DOMAIN,
                script_mode=SCRIPT_MODE_PARALLEL,
                logger=_LOGGER,
            )

        for room_id, room in self.rooms.items():
            room_name = room.get(CONF_NAME, room_id)
            for device_id, device in room[CONF_DEVICES].items():
                for command, actions in device[CONF_COMMANDS].items():
                    self._command_scripts[(room_id, "device", device_id, command)] = script(
                        actions, f"{room_name} {device_id} {command}"
                    )
            for activity_id, activity in room[CONF_ACTIVITIES].items():
                activity_name = activity.get(CONF_NAME, activity_id)
                for key in (CONF_ON_START, CONF_ON_STOP):
                    if activity.get(key):
                        self._scripts[(room_id, activity_id, key)] = script(
                            activity[key], f"{room_name} {activity_name} {key}"
                        )
                for command, actions in activity[CONF_COMMANDS].items():
                    self._command_scripts[(room_id, "activity", activity_id, command)] = (
                        script(actions, f"{room_name} {activity_name} {command}")
                    )

    @callback
    def _update_issues(self) -> None:
        """Raise a repair issue for every referenced entity that does not exist."""
        prefix = f"missing_entity_{self.entry.entry_id}_"
        wanted: set[str] = set()
        for ref in find_missing_entities(self.hass, {CONF_ROOMS: self.rooms}):
            issue_id = f"{prefix}{ref.room_id}_{ref.path}"
            wanted.add(issue_id)
            _LOGGER.warning(
                "Room '%s': %s refers to unknown entity %s",
                ref.room_id,
                ref.path,
                ref.entity_id,
            )
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="missing_entity",
                translation_placeholders={
                    "entity_id": ref.entity_id,
                    "room": self.rooms[ref.room_id].get(CONF_NAME, ref.room_id),
                    "path": ref.path,
                },
            )
        registry = ir.async_get(self.hass)
        for (domain, issue_id) in list(registry.issues):
            if domain == DOMAIN and issue_id.startswith(prefix) and issue_id not in wanted:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    # ------------------------------------------------------------------
    # Persistence of the room state across restarts
    # ------------------------------------------------------------------

    async def _async_restore(self) -> None:
        stored = await self._store.async_load() or {}
        self._sources = {
            entity_id: [str(s) for s in sources]
            for entity_id, sources in (stored.get("sources") or {}).items()
            if isinstance(sources, list)
        }
        for room_id, data in stored.get(CONF_ROOMS, {}).items():
            if room_id not in self.rooms:
                continue
            rt = self.runtime(room_id)
            rt.last_activity = data.get("last_activity")
            activity = data.get("activity")
            state = _RESTORED_STATES.get(data.get("state"))
            if activity in self.rooms[room_id][CONF_ACTIVITIES] and state:
                rt.activity = activity
                rt.state = state
                if data.get("state") != state:
                    rt.error = "Interrupted by a Home Assistant restart"
                else:
                    rt.error = data.get("error")

    @callback
    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._data_to_store, 1)

    @callback
    def _data_to_store(self) -> dict[str, Any]:
        return {
            CONF_ROOMS: {
                room_id: {
                    "activity": rt.activity,
                    "state": rt.state,
                    "error": rt.error,
                    "last_activity": rt.last_activity,
                }
                for room_id, rt in self._runtime.items()
            },
            "sources": self._sources,
        }

    @callback
    def _changed(self) -> None:
        self._schedule_save()
        self.async_update_listeners()

    @callback
    def async_update_listeners(self) -> None:
        """Update the entities and tell subscribed remote controls."""
        super().async_update_listeners()
        async_dispatcher_send(self.hass, SIGNAL_ROOMS_UPDATED)

    async def async_shutdown(self) -> None:
        """Cancel running work when the entry unloads."""
        if self._unsub_sources is not None:
            self._unsub_sources()
            self._unsub_sources = None
        for rt in self._runtime.values():
            for task in [rt.task, *rt.pending_cuts.values()]:
                if task and not task.done():
                    task.cancel()
        await self._store.async_save(self._data_to_store())
        await super().async_shutdown()

    # ------------------------------------------------------------------
    # Remembered source lists
    # ------------------------------------------------------------------

    @property
    def source_lists(self) -> dict[str, list[str]]:
        """Last known source list per media player of the configuration."""
        return dict(self._sources)

    def _track_sources(self) -> None:
        """Follow the source lists of the configured media players."""
        if self._unsub_sources is not None:
            self._unsub_sources()
            self._unsub_sources = None
        players = sorted(
            {
                device[CONF_ENTITY_ID]
                for room in self.rooms.values()
                for device in room[CONF_DEVICES].values()
                if device[CONF_ENTITY_ID].startswith("media_player.")
            }
        )
        changed = False
        for entity_id in [e for e in self._sources if e not in players]:
            del self._sources[entity_id]
            changed = True
        for entity_id in players:
            changed |= self._remember_sources(entity_id, self.hass.states.get(entity_id))
        if changed:
            self._schedule_save()
        if players:
            self._unsub_sources = async_track_state_change_event(
                self.hass, players, self._source_state_changed
            )

    @callback
    def _source_state_changed(self, event: Event[EventStateChangedData]) -> None:
        if self._remember_sources(event.data["entity_id"], event.data["new_state"]):
            self._schedule_save()

    def _remember_sources(self, entity_id: str, state: State | None) -> bool:
        """Keep a non-empty source list; True when it changed."""
        sources = state.attributes.get("source_list") if state is not None else None
        if not isinstance(sources, list) or not sources:
            return False
        sources = [str(s) for s in sources]
        if self._sources.get(entity_id) == sources:
            return False
        self._sources[entity_id] = sources
        return True

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_start_activity(self, room_id: str, activity: str) -> None:
        """Start an activity (id or name) in a room."""
        if room_id not in self.rooms:
            _LOGGER.error("Room '%s' not found", room_id)
            return
        activity_id = self.resolve_activity(room_id, activity)
        if activity_id is None:
            _LOGGER.error("Activity '%s' not found in room '%s'", activity, room_id)
            return
        await self._async_run_command(
            room_id, ("start", activity_id), lambda: self._async_start(room_id, activity_id)
        )

    async def async_stop_activity(self, room_id: str) -> None:
        """Stop whatever runs in a room."""
        if room_id not in self.rooms:
            _LOGGER.error("Room '%s' not found", room_id)
            return
        await self._async_run_command(
            room_id, ("stop", None), lambda: self._async_stop(room_id)
        )

    async def async_toggle_activity(self, room_id: str, activity: str | None = None) -> None:
        """Stop the room if something runs there, otherwise start an activity.

        Without an activity, the last successfully started one is used, and
        the first configured one if there is none yet.
        """
        if room_id not in self.rooms:
            _LOGGER.error("Room '%s' not found", room_id)
            return
        rt = self.runtime(room_id)
        if rt.activity is not None and rt.state != ACTIVITY_STATE_STOPPING:
            await self.async_stop_activity(room_id)
            return
        target = activity or self.default_activity(room_id)
        if target is None:
            _LOGGER.error("Room '%s' has no activity to start", room_id)
            return
        await self.async_start_activity(room_id, target)

    def default_activity(self, room_id: str) -> str | None:
        """Activity a plain "on" starts.

        The room's ``default_activity``, else the last one, else the first
        in order.
        """
        room = self.rooms.get(room_id, {})
        activities = room.get(CONF_ACTIVITIES, {})
        if room.get(CONF_DEFAULT_ACTIVITY) in activities:
            return room[CONF_DEFAULT_ACTIVITY]
        last = self.runtime(room_id).last_activity
        if last in activities:
            return last
        return next(iter(activities), None)

    async def _async_run_command(
        self,
        room_id: str,
        command: tuple[str, str | None],
        factory: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Cancel the running command of the room and run a new one.

        Repeating the command that is already running just waits for it. The
        last command wins: one that is still waiting for the previous one to
        end is dropped when another command arrives.
        """
        rt = self.runtime(room_id)
        running = rt.task if rt.task and not rt.task.done() else None

        if running is not None and rt.command == command and not running.cancelling():
            await self._await_task(running)
            return
        if running is not None and not running.cancelling():
            _LOGGER.info("Room '%s': cancelling running %s", room_id, rt.command[0])
            running.cancel()
        rt.generation += 1
        generation = rt.generation

        async with rt.lock:
            if rt.generation != generation:
                _LOGGER.debug("Room '%s': %s dropped, a newer command follows", room_id, command[0])
                return
            token = _current_room.set(rt)
            try:
                task = self.hass.async_create_background_task(
                    factory(), f"{DOMAIN} {room_id} {command[0]}"
                )
            finally:
                _current_room.reset(token)
            rt.task = task
            rt.command = command
            await self._await_task(task)

    @staticmethod
    async def _await_task(task: asyncio.Task) -> None:
        """Await a command task; its cancellation by a newer command is no error."""
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise
            # The task was cancelled by another command; wait until it is gone
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # ------------------------------------------------------------------
    # Remote control
    # ------------------------------------------------------------------

    def room_view(self, room_id: str) -> dict[str, Any]:
        """Everything a remote control needs to show a room."""
        room = self.rooms[room_id]
        rt = self.runtime(room_id)
        activities: dict[str, Any] = room[CONF_ACTIVITIES]
        activity = activities.get(rt.activity) if rt.activity else None
        return {
            "entry_id": self.entry.entry_id,
            "room": room_id,
            "name": room.get(CONF_NAME, room_id),
            "area_id": room.get(CONF_AREA_ID),
            "state": rt.state,
            "activity": rt.activity,
            "error": rt.error,
            "warnings": list(rt.warnings),
            "progress": list(rt.progress),
            "current": dict(rt.current) if rt.current else None,
            "cooling": list(rt.cooling.values()),
            "default_activity": self.default_activity(room_id),
            "activities": activity_list(room),
            "remote": remote_view(room, activity) if activity is not None else None,
        }

    async def async_send_command(
        self,
        room_id: str,
        command: str,
        *,
        value: Any = None,
        device_id: str | None = None,
        context: Context | None = None,
    ) -> None:
        """Run a remote command on the devices of the running activity.

        With ``device_id`` the command goes to that device, even while
        nothing runs. Errors are raised, so the caller sees them.
        """
        room = self.rooms[room_id]
        devices: dict[str, Any] = room[CONF_DEVICES]
        activity_id = self.runtime(room_id).activity
        activity = room[CONF_ACTIVITIES].get(activity_id) if activity_id else None
        placeholders = {"room": room.get(CONF_NAME, room_id), "command": command}
        variables = {"command": command, "value": value}

        if device_id is not None:
            if device_id not in devices:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_device",
                    translation_placeholders={**placeholders, "device": device_id},
                )
        else:
            if activity is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="no_activity",
                    translation_placeholders=placeholders,
                )
            if command in activity[CONF_COMMANDS]:
                script = self._command_scripts[(room_id, "activity", activity_id, command)]
                await self._async_run_command_script(script, variables, context)
                return
            device_id = route(room, activity, command)
            if device_id is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_command",
                    translation_placeholders=placeholders,
                )

        device = devices[device_id]
        entity_id = device[CONF_ENTITY_ID]
        ready = device.get(CONF_READY)
        if ready and not self._is_ready(entity_id, ready):
            # The connection got lost while the activity runs: bring it back
            # before the command goes nowhere
            try:
                await self._async_wait_ready(entity_id, ready, f"device '{device_id}'")
            except ActivityAborted as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="device_not_ready",
                    translation_placeholders={"command": command, "reason": str(err)},
                ) from err
        if command in device[CONF_COMMANDS]:
            script = self._command_scripts[(room_id, "device", device_id, command)]
            await self._async_run_command_script(
                script, {**variables, "entity_id": entity_id}, context
            )
            return

        remote = device.get(CONF_REMOTE_ENTITY)
        try:
            call = (
                remote_call(command, remote, self._platform_of(remote)) if remote else None
            ) or builtin_call(command, entity_id, self.hass.states.get(entity_id), value)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        if call is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_command",
                translation_placeholders=placeholders,
            )
        domain, service, data = call
        _LOGGER.debug("Room '%s': %s -> %s.%s %s", room_id, command, domain, service, data)
        try:
            async with asyncio.timeout(self.service_timeout):
                await self.hass.services.async_call(
                    domain, service, data, blocking=True, context=context
                )
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_timeout",
                translation_placeholders={"command": command, "target": entity_id},
            ) from err

    async def _async_run_command_script(
        self, script: Script, variables: dict[str, Any], context: Context | None
    ) -> None:
        try:
            async with asyncio.timeout(self.service_timeout):
                await script.async_run(run_variables=variables, context=context or Context())
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_timeout",
                translation_placeholders={"command": variables["command"], "target": script.name},
            ) from err

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    async def _async_start(self, room_id: str, activity_id: str) -> None:
        rt = self.runtime(room_id)
        room = self.rooms[room_id]
        activity = room[CONF_ACTIVITIES][activity_id]
        devices: dict[str, Any] = room[CONF_DEVICES]
        new_devices: list[str] = activity[CONF_DEVICES]
        steps: list[dict[str, Any]] = activity[CONF_STEPS]
        context = Context()

        previous = rt.activity if rt.activity != activity_id else None
        _LOGGER.info(
            "Room '%s': starting '%s'%s",
            room_id,
            activity_id,
            f" (switching from '{previous}')" if previous else "",
        )

        rt.activity = activity_id
        rt.state = ACTIVITY_STATE_STARTING
        rt.error = None
        rt.warnings = []
        total = len(new_devices) + len(steps)
        rt.progress = (0, total)
        ir.async_delete_issue(self.hass, DOMAIN, self._aborted_issue_id(room_id))
        self._changed()

        needed_switches = power_switches(devices, new_devices)
        for switch in needed_switches:
            self._cancel_cut(rt, switch)

        hook: asyncio.Task | None = None
        try:
            if previous is not None:
                await self._async_switch_off_unused(room_id, previous, new_devices, context)

            # Switches that were off: their devices need their boot time
            powered = {s for s in needed_switches if self._is_off(s)}
            if needed_switches:
                self._doing(rt, "power_on")
                await self._async_call(
                    "homeassistant",
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: needed_switches},
                    context,
                    f"power on {', '.join(needed_switches)}",
                )
            powered_at = self._now()

            hook = self._start_hook(room_id, activity_id, CONF_ON_START, context)

            done = 0
            for device_id in new_devices:
                device = devices[device_id]
                if device.get(CONF_POWER_SWITCH) in powered and device[CONF_DELAY_AFTER_POWER]:
                    # Devices on the same switch boot in parallel
                    remaining = device[CONF_DELAY_AFTER_POWER] - (self._now() - powered_at)
                    if remaining > 0:
                        _LOGGER.debug(
                            "Waiting %.1f s for %s to boot", remaining, device[CONF_ENTITY_ID]
                        )
                        self._doing(rt, "boot", name=self._device_name(device), seconds=remaining)
                        await self._async_sleep(remaining)
                ready = device.get(CONF_READY)
                if ready:
                    reload = None
                    if device.get(CONF_POWER_SWITCH) in powered and ready[CONF_RELOAD_INTEGRATION]:
                        # The integration last saw the device without power and
                        # may still report a stale state ("off" instead of
                        # unavailable): reload it once the device has booted
                        task = self._reload_integration_of(
                            ready.get(CONF_ENTITY_ID) or device[CONF_ENTITY_ID]
                        )
                        if task is not None:
                            self._doing(rt, "reload", name=self._device_name(device))
                            try:
                                # A reload that hangs must not hold up the start
                                async with asyncio.timeout(ready[CONF_TIMEOUT]):
                                    await self._await_task(task)
                            except TimeoutError:
                                self._warn(
                                    f"device '{device_id}': reloading its integration did not"
                                    f" finish within {ready[CONF_TIMEOUT]:g} s"
                                )
                        reload = False
                    await self._async_wait_ready(
                        device[CONF_ENTITY_ID],
                        ready,
                        f"device '{device_id}'",
                        reload=reload,
                        name=self._device_name(device),
                    )
                if self._is_off(device[CONF_ENTITY_ID]):
                    self._doing(rt, "turn_on", name=self._device_name(device))
                    await self._async_power_on(device[CONF_ENTITY_ID], context)
                    if device[CONF_DELAY_AFTER_ON]:
                        self._doing(
                            rt,
                            "warm_up",
                            name=self._device_name(device),
                            seconds=device[CONF_DELAY_AFTER_ON],
                        )
                        await self._async_sleep(device[CONF_DELAY_AFTER_ON])
                done += 1
                rt.progress = (done, total)
                self.async_update_listeners()

            for idx, step in enumerate(steps, 1):
                _LOGGER.debug("Room '%s': step %d/%d %s", room_id, idx, len(steps), step)
                position = {"step": idx, "steps": len(steps), "step_type": step[CONF_TYPE]}
                device_id = step.get(CONF_DEVICE)
                name = self._device_name(devices[device_id]) if device_id else None
                self._doing(rt, "step", name=name, **position)
                await self._async_execute_step(room, step, context, name=name)
                if step[CONF_DELAY_AFTER]:
                    self._doing(rt, "wait", seconds=step[CONF_DELAY_AFTER], **position)
                    await self._async_sleep(step[CONF_DELAY_AFTER])
                done += 1
                rt.progress = (done, total)
                self.async_update_listeners()

            if hook is not None:
                if not hook.done():
                    self._doing(rt, "hooks", hook=CONF_ON_START)
                await hook
        except asyncio.CancelledError:
            if hook is not None:
                hook.cancel()
            rt.current = None
            raise
        except Exception as err:  # noqa: BLE001 - the room must not stay "starting"
            if hook is not None:
                hook.cancel()
            rt.current = None
            rt.state = ACTIVITY_STATE_ERROR
            rt.error = str(err) or type(err).__name__
            if isinstance(err, ActivityAborted):
                _LOGGER.error("Room '%s': start of '%s' aborted: %s", room_id, activity_id, err)
            else:
                _LOGGER.exception("Room '%s': start of '%s' failed", room_id, activity_id)
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._aborted_issue_id(room_id),
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="activity_aborted",
                translation_placeholders={
                    "room": room.get(CONF_NAME, room_id),
                    "activity": self.activity_name(room_id, activity_id),
                    "reason": rt.error,
                },
            )
            self._changed()
            return

        rt.state = ACTIVITY_STATE_ACTIVE
        rt.last_activity = activity_id
        rt.progress = (total, total)
        rt.current = None
        self._changed()
        _LOGGER.info("Room '%s': '%s' is active", room_id, activity_id)

    async def _async_switch_off_unused(
        self, room_id: str, previous: str, new_devices: list[str], context: Context
    ) -> None:
        """Smart switching: turn off what the next activity does not need."""
        rt = self.runtime(room_id)
        room = self.rooms[room_id]
        devices = room[CONF_DEVICES]
        old = room[CONF_ACTIVITIES].get(previous, {}).get(CONF_DEVICES, [])
        unused = [d for d in reversed(old) if d not in new_devices]
        if not unused:
            return
        _LOGGER.info("Room '%s': switching off devices no longer needed: %s", room_id, unused)

        cooldown: dict[str, float] = {}
        cooling: dict[str, list[str]] = {}
        for device_id in unused:
            device = devices[device_id]
            self._doing(rt, "turn_off", name=self._device_name(device))
            await self._async_power_off(device[CONF_ENTITY_ID], context)
            switch = device.get(CONF_POWER_SWITCH)
            if switch:
                cooldown[switch] = max(cooldown.get(switch, 0), device[CONF_DELAY_AFTER_OFF])
                if device[CONF_DELAY_AFTER_OFF]:
                    cooling.setdefault(switch, []).append(self._device_name(device))

        still_needed = set(power_switches(devices, new_devices))
        still_needed |= self._switches_used_elsewhere(rt)
        for switch, delay in cooldown.items():
            if switch not in still_needed:
                self._schedule_cut(rt, room_id, switch, delay, cooling.get(switch, []))

    def _schedule_cut(
        self, rt: RoomRuntime, room_id: str, switch: str, delay: float, names: list[str]
    ) -> None:
        """Cut a power switch in the background after the cool-down.

        ``names`` are the devices that cool down meanwhile; the card shows
        them with the time the power goes off.
        """
        self._cancel_cut(rt, switch)
        if delay > 0:
            until = dt_util.utcnow() + timedelta(seconds=delay)
            rt.cooling[switch] = {
                "outlet": self._entity_name(switch),
                "names": names,
                "until": until.isoformat(),
            }
        rt.pending_cuts[switch] = task = self.hass.async_create_background_task(
            self._async_cut_later(rt, switch, delay),
            f"{DOMAIN} {room_id} cut {switch}",
        )

        @callback
        def _done(_: asyncio.Task) -> None:
            # Cut, kept for another room, or cancelled by a new start
            if rt.pending_cuts.get(switch) in (task, None) and rt.cooling.pop(switch, None):
                self.async_update_listeners()

        task.add_done_callback(_done)

    async def _async_cut_later(self, rt: RoomRuntime, switch: str, delay: float) -> None:
        if delay:
            _LOGGER.debug("Cutting power of %s in %s s", switch, delay)
            await self._async_sleep(delay)
        rt.pending_cuts.pop(switch, None)
        if switch in self._switches_used_elsewhere(rt):
            _LOGGER.debug("Keeping %s on, another room uses it", switch)
            return
        with contextlib.suppress(ActivityAborted):
            await self._async_call(
                "homeassistant",
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: switch},
                Context(),
                f"power off {switch}",
            )

    def _switches_used_elsewhere(self, rt: RoomRuntime) -> set[str]:
        """Power switches the activities of all other rooms need.

        Rooms that are stopping do not count: they cut their switches
        themselves once they are done.
        """
        coordinators = [
            c for c in self.hass.data.get(DOMAIN, {}).values() if isinstance(c, AVScenesCoordinator)
        ]
        if self not in coordinators:
            coordinators.append(self)
        switches: set[str] = set()
        for coordinator in coordinators:
            for room_id, other in coordinator._runtime.items():
                if other is rt or other.activity is None or other.state == ACTIVITY_STATE_STOPPING:
                    continue
                room = coordinator.rooms.get(room_id)
                activity = room[CONF_ACTIVITIES].get(other.activity) if room else None
                if activity is not None:
                    switches.update(
                        power_switches(room[CONF_DEVICES], activity[CONF_DEVICES])
                    )
        return switches

    @staticmethod
    def _cancel_cut(rt: RoomRuntime, switch: str) -> None:
        task = rt.pending_cuts.pop(switch, None)
        rt.cooling.pop(switch, None)
        if task is not None and not task.done():
            task.cancel()

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------

    async def _async_stop(self, room_id: str) -> None:
        rt = self.runtime(room_id)
        if rt.activity is None:
            _LOGGER.debug("Room '%s': nothing to stop", room_id)
            return

        room = self.rooms[room_id]
        activity_id = rt.activity
        activity = room[CONF_ACTIVITIES].get(activity_id)
        context = Context()
        _LOGGER.info("Room '%s': stopping '%s'", room_id, activity_id)

        rt.state = ACTIVITY_STATE_STOPPING
        self._changed()

        if activity is not None:
            devices = room[CONF_DEVICES]
            device_ids: list[str] = activity[CONF_DEVICES]
            hook = self._start_hook(room_id, activity_id, CONF_ON_STOP, context)
            try:
                # Power switch -> cool-down its devices still need, and who cools
                cooldown: dict[str, float] = {}
                cooling: dict[str, list[str]] = {}
                for device_id in reversed(device_ids):
                    device = devices[device_id]
                    entity_id = device[CONF_ENTITY_ID]
                    delay = device[CONF_DELAY_AFTER_OFF]
                    if self._is_off(entity_id):
                        delay = self._remaining_cooldown(entity_id, delay)
                    else:
                        self._doing(rt, "turn_off", name=self._device_name(device))
                        await self._async_power_off(entity_id, context)
                    if switch := device.get(CONF_POWER_SWITCH):
                        cooldown[switch] = max(cooldown.get(switch, 0.0), delay)
                        if delay > 0:
                            cooling.setdefault(switch, []).append(self._device_name(device))

                used_elsewhere = self._switches_used_elsewhere(rt)
                switches = [
                    s
                    for s in reversed(power_switches(devices, device_ids))
                    if s not in used_elsewhere
                ]
                for switch in switches:
                    self._cancel_cut(rt, switch)
                now = [s for s in switches if cooldown.get(s, 0) <= 0]
                if now:
                    self._doing(rt, "power_off")
                    with contextlib.suppress(ActivityAborted):
                        await self._async_call(
                            "homeassistant",
                            SERVICE_TURN_OFF,
                            {ATTR_ENTITY_ID: now},
                            context,
                            f"power off {', '.join(now)}",
                        )
                # The rest after the cool-down, without keeping the room busy
                for switch in switches:
                    if switch not in now:
                        self._schedule_cut(
                            rt, room_id, switch, cooldown[switch], cooling.get(switch, [])
                        )
                if hook is not None:
                    if not hook.done():
                        self._doing(rt, "hooks", hook=CONF_ON_STOP)
                    await hook
            except asyncio.CancelledError:
                if hook is not None:
                    hook.cancel()
                rt.current = None
                raise
            except Exception as err:  # noqa: BLE001 - the room must not stay "stopping"
                if hook is not None:
                    hook.cancel()
                rt.current = None
                _LOGGER.exception("Room '%s': stop of '%s' failed", room_id, activity_id)
                rt.state = ACTIVITY_STATE_ERROR
                rt.error = str(err) or type(err).__name__
                self._changed()
                return

        rt.activity = None
        rt.state = ACTIVITY_STATE_IDLE
        rt.error = None
        rt.progress = (0, 0)
        rt.current = None
        ir.async_delete_issue(self.hass, DOMAIN, self._aborted_issue_id(room_id))
        self._changed()
        _LOGGER.info("Room '%s': '%s' stopped", room_id, activity_id)

    async def _async_sleep(self, seconds: float) -> None:
        """Wait between actions (a seam for tests)."""
        await asyncio.sleep(seconds)

    def _now(self) -> float:
        """Monotonic clock in seconds (a seam for tests)."""
        return self.hass.loop.time()

    def _remaining_cooldown(self, entity_id: str, delay: float) -> float:
        """Cool-down still left for a device that was already off."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state == STATE_UNAVAILABLE or not delay:
            return 0
        elapsed = (dt_util.utcnow() - state.last_changed).total_seconds()
        return max(0.0, delay - elapsed)

    # ------------------------------------------------------------------
    # Readiness
    # ------------------------------------------------------------------

    @staticmethod
    def _state_ok(state: State | None, wanted: list[str] | None) -> bool:
        if state is None:
            return False
        if wanted:
            return state.state in wanted
        return state.state != STATE_UNAVAILABLE

    def _is_ready(self, entity_id: str, options: dict[str, Any]) -> bool:
        target = options.get(CONF_ENTITY_ID) or entity_id
        return self._state_ok(self.hass.states.get(target), options.get(CONF_STATE))

    async def _async_wait_ready(
        self,
        entity_id: str,
        options: dict[str, Any],
        label: str,
        *,
        reload: bool | None = None,
        name: str | None = None,
    ) -> bool:
        """Wait until an entity is ready.

        Ready means it exists and is not unavailable, or, with ``state``, has
        one of those states. ``entity_id`` in the options checks another
        entity than the given one.

        Returns False on a timeout with ``on_timeout: continue`` and raises
        ActivityAborted on a timeout with ``on_timeout: abort``. ``name`` is
        what the card shows while it waits during a start.
        """
        entity_id = options.get(CONF_ENTITY_ID) or entity_id
        wanted: list[str] | None = options.get(CONF_STATE)
        if self._state_ok(self.hass.states.get(entity_id), wanted):
            return True

        timeout: float = options[CONF_TIMEOUT]
        loop = asyncio.get_running_loop()
        ready: asyncio.Future[None] = loop.create_future()

        @callback
        def _state_changed(event: Event[EventStateChangedData]) -> None:
            if self._state_ok(event.data["new_state"], wanted) and not ready.done():
                ready.set_result(None)

        unsub: CALLBACK_TYPE = async_track_state_change_event(
            self.hass, [entity_id], _state_changed
        )
        retry: asyncio.Task | None = None
        try:
            if options[CONF_RELOAD_INTEGRATION] if reload is None else reload:
                self._reload_integration_of(entity_id)
            if options[CONF_RELOAD_INTEGRATION]:
                retry = self.hass.async_create_background_task(
                    self._async_retry_reload(entity_id), f"{DOMAIN} retry {entity_id}"
                )
            # The entity may have come up between the first check and subscribing
            if self._state_ok(self.hass.states.get(entity_id), wanted):
                return True
            _LOGGER.info(
                "Waiting up to %s s for %s to become %s",
                timeout,
                entity_id,
                " or ".join(wanted) if wanted else "available",
            )
            if (rt := _current_room.get()) is not None:
                self._doing(
                    rt, "ready", name=name or self._entity_name(entity_id), seconds=timeout
                )
            try:
                async with asyncio.timeout(timeout):
                    await ready
            except TimeoutError:
                message = (
                    f"{label}: {entity_id} not "
                    f"{' or '.join(wanted) if wanted else 'available'} after {timeout:g} s"
                )
                if options[CONF_ON_TIMEOUT] == ON_TIMEOUT_ABORT:
                    raise ActivityAborted(message) from None
                _LOGGER.warning("%s, continuing", message)
                return False
            _LOGGER.info("%s is available", entity_id)
            return True
        finally:
            # A started reload is left to finish on its own
            unsub()
            if retry is not None:
                retry.cancel()

    async def _async_retry_reload(self, entity_id: str) -> None:
        """Reload an entity's integration again while it is in setup_retry.

        Runs until cancelled. A reload that is still running is waited for, so
        one attempt follows the other with a pause in between.
        """
        entity = er.async_get(self.hass).async_get(entity_id)
        if entity is None or entity.config_entry_id is None:
            return
        entry_id = entity.config_entry_id
        while True:
            running = self._reloads.get(entry_id)
            if running is not None and not running.done():
                await asyncio.shield(running)
            await asyncio.sleep(RELOAD_RETRY_INTERVAL)
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                return
            if entry.state is ConfigEntryState.SETUP_RETRY:
                _LOGGER.debug("%s is still not set up, reloading it again", entry.title)
                self._reload_integration_of(entity_id)

    def _reload_integration_of(self, entity_id: str) -> asyncio.Task | None:
        """Reload the config entry that provides an entity; a running reload is reused.

        Resets the back-off of an entry in setup_retry. The registry keeps the
        entry even while the entity has no state.
        """
        entity = er.async_get(self.hass).async_get(entity_id)
        if entity is None or entity.config_entry_id is None:
            _LOGGER.warning("Cannot reload integration of %s: not in the entity registry", entity_id)
            return None
        entry_id = entity.config_entry_id
        running = self._reloads.get(entry_id)
        if running is not None and not running.done():
            return running
        _LOGGER.info("Reloading config entry %s to bring up %s", entry_id, entity_id)

        async def _reload() -> None:
            try:
                await self.hass.config_entries.async_reload(entry_id)
            except Exception:  # noqa: BLE001 - only logged, the wait decides
                _LOGGER.exception("Reloading config entry %s failed", entry_id)

        task = self.hass.async_create_background_task(_reload(), f"{DOMAIN} reload {entry_id}")
        self._reloads[entry_id] = task
        return task

    # ------------------------------------------------------------------
    # Steps and service calls
    # ------------------------------------------------------------------

    async def _async_execute_step(
        self,
        room: dict[str, Any],
        step: dict[str, Any],
        context: Context,
        *,
        name: str | None = None,
    ) -> None:
        step_type = step[CONF_TYPE]
        entity_id = None
        if CONF_DEVICE in step:
            entity_id = room[CONF_DEVICES][step[CONF_DEVICE]][CONF_ENTITY_ID]

        if step_type == STEP_TYPE_DELAY:
            return
        if step_type == STEP_TYPE_WAIT_AVAILABLE:
            await self._async_wait_ready(
                entity_id or step[CONF_ENTITY_ID],
                step,
                f"step {step.get('id', '')}".strip(),
                name=name,
            )
            return
        if step_type == STEP_TYPE_POWER_ON:
            await self._async_power_on(entity_id, context)
            return
        if step_type == STEP_TYPE_POWER_OFF:
            await self._async_power_off(entity_id, context)
            return

        call = step_service(step_type, step, entity_id)
        if call is None:
            return
        domain, service, data, target = call
        await self._async_call(domain, service, data, context, step_type, target)

    def _is_off(self, entity_id: str) -> bool:
        state = self.hass.states.get(entity_id)
        return state is None or state.state in _OFF_STATES

    def _platform_of(self, entity_id: str) -> str | None:
        """The integration that provides an entity, e.g. apple_tv."""
        entry = er.async_get(self.hass).async_get(entity_id)
        return entry.platform if entry is not None else None

    def _entity_unavailable(self, entity_id: str) -> bool:
        """True when the integration reports its entity as not available.

        The state may still show an older value; Home Assistant then drops a
        service call for the entity with only a log warning.
        """
        component = self.hass.data.get(DATA_INSTANCES, {}).get(entity_id.split(".")[0])
        entity = component.get_entity(entity_id) if component is not None else None
        return entity is not None and not entity.available

    async def _async_power_on(self, entity_id: str, context: Context) -> None:
        if not can_switch(self.hass, entity_id, on=True):
            _LOGGER.debug("%s cannot be switched on, skipping", entity_id)
            return
        if self._entity_unavailable(entity_id):
            self._warn(f"turn on: {entity_id} is not reachable, it was not switched on")
            return
        domain, service = power_service(entity_id, on=True)
        await self._async_call(domain, service, {ATTR_ENTITY_ID: entity_id}, context, "turn on")

    async def _async_power_off(self, entity_id: str, context: Context) -> None:
        if not can_switch(self.hass, entity_id, on=False):
            _LOGGER.debug("%s cannot be switched off, skipping", entity_id)
            return
        domain, service = power_service(entity_id, on=False)
        await self._async_call(domain, service, {ATTR_ENTITY_ID: entity_id}, context, "turn off")

    async def _async_call(
        self,
        domain: str,
        service: str,
        data: dict[str, Any],
        context: Context,
        label: str,
        target: dict[str, Any] | None = None,
    ) -> None:
        """Call a service and wait for it, bounded by the service timeout.

        Failures are logged and recorded as warnings; the activity goes on.
        """
        try:
            async with asyncio.timeout(self.service_timeout):
                await self.hass.services.async_call(
                    domain,
                    service,
                    data,
                    blocking=True,
                    context=context,
                    target=target,
                )
        except TimeoutError:
            self._warn(f"{label}: {domain}.{service} did not finish within {self.service_timeout:g} s")
        except Exception as err:  # noqa: BLE001 - any failing device must not stop the rest
            self._warn(f"{label}: {domain}.{service} failed: {err}")

    def _doing(
        self,
        rt: RoomRuntime,
        kind: str,
        *,
        name: str | None = None,
        seconds: float | None = None,
        **extra: Any,
    ) -> None:
        """Record what a start or stop is busy with and tell the card.

        ``kind`` is power_on, boot, reload, ready, turn_on, warm_up, step,
        wait, hooks, turn_off or power_off; ``name`` the device or entity;
        ``seconds`` a wait, sent as the time it ends (``until``).
        """
        current: dict[str, Any] = {"kind": kind, "name": name, **extra}
        if seconds is not None:
            current["until"] = (dt_util.utcnow() + timedelta(seconds=seconds)).isoformat()
        rt.current = current
        self.async_update_listeners()

    def _entity_name(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        return (state.name if state is not None else None) or entity_id

    def _device_name(self, device: dict[str, Any]) -> str:
        """The name of a device as the card shows it."""
        return device.get(CONF_NAME) or self._entity_name(device[CONF_ENTITY_ID])

    @staticmethod
    def _warn(message: str) -> None:
        _LOGGER.warning(message)
        if (rt := _current_room.get()) is not None:
            rt.warnings.append(message)

    def _start_hook(
        self, room_id: str, activity_id: str, key: str, context: Context
    ) -> asyncio.Task | None:
        script = self._scripts.get((room_id, activity_id, key))
        if script is None:
            return None

        async def _run() -> None:
            try:
                await script.async_run(context=context)
            except Exception as err:  # noqa: BLE001 - hooks must not break the activity
                self._warn(f"{key} failed: {err}")

        return self.hass.async_create_task(_run(), f"{DOMAIN} {room_id} {key}")

    def _aborted_issue_id(self, room_id: str) -> str:
        return f"activity_aborted_{self.entry.entry_id}_{room_id}"
