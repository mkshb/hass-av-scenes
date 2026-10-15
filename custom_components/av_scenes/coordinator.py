"""Activity engine for the AV Scenes integration.

Starting an activity
    1. Smart switching: devices of the previous activity that the new one does
       not use are switched off. Their power switches are cut in the
       background once every device on them had its ``delay_after_off``.
    2. Power: all power switches the new activity needs are switched on at
       once so the devices boot in parallel.
    3. ``on_start`` actions start running alongside.
    4. Per device, in order: readiness check (``ready``), turn on (only when
       it is off), ``delay_after_on`` (only when it was switched on).
    5. Steps.
    6. Wait for ``on_start``; the activity is ``active``.

    A readiness check or ``wait_available`` step with ``on_timeout: abort``
    stops the start; the room goes to ``error`` and never to ``active``.

Stopping an activity
    ``on_stop`` actions run alongside; devices are switched off in reverse
    order, each followed by its ``delay_after_off``; power switches last.

A new command for a room cancels whatever runs there (a stop during a long
start, a different activity while starting).
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import contextlib
from contextvars import ContextVar
from dataclasses import dataclass, field
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
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
    callback,
)
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
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
    CONF_BRIGHTNESS_PCT,
    CONF_COLOR_TEMP_KELVIN,
    CONF_DATA,
    CONF_DELAY_AFTER_OFF,
    CONF_DELAY_AFTER_ON,
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
    CONF_ROOMS,
    CONF_SOUND_MODE,
    CONF_SOURCE,
    CONF_STEPS,
    CONF_TARGET,
    CONF_TILT_POSITION,
    CONF_TIMEOUT,
    CONF_TRANSITION,
    CONF_TYPE,
    CONF_VOLUME_LEVEL,
    DEFAULT_SERVICE_TIMEOUT,
    DOMAIN,
    ON_TIMEOUT_ABORT,
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
from .model import CONF_DELAY_AFTER, async_validate_config, find_missing_entities

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

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
    # power switch -> background task that cuts it after the cool-down
    pending_cuts: dict[str, asyncio.Task] = field(default_factory=dict)


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
        self._scripts: dict[tuple[str, str, str], Script] = {}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.state"
        )
        self._restored = False

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
        """What the entities are made of: rooms and activities with their names."""
        return [
            (
                room_id,
                room.get(CONF_NAME, room_id),
                [
                    (activity_id, activity.get(CONF_NAME, activity_id))
                    for activity_id, activity in (room.get(CONF_ACTIVITIES) or {}).items()
                ],
            )
            for room_id, room in rooms.items()
        ]

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

        return config

    def _build_scripts(self) -> None:
        self._scripts = {}
        for room_id, room in self.rooms.items():
            for activity_id, activity in room[CONF_ACTIVITIES].items():
                for key in (CONF_ON_START, CONF_ON_STOP):
                    if activity.get(key):
                        self._scripts[(room_id, activity_id, key)] = Script(
                            self.hass,
                            activity[key],
                            f"AV Scenes {room.get(CONF_NAME, room_id)} "
                            f"{activity.get(CONF_NAME, activity_id)} {key}",
                            DOMAIN,
                            script_mode=SCRIPT_MODE_PARALLEL,
                            logger=_LOGGER,
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
            }
        }

    @callback
    def _changed(self) -> None:
        self._schedule_save()
        self.async_update_listeners()

    async def async_shutdown(self) -> None:
        """Cancel running work when the entry unloads."""
        for rt in self._runtime.values():
            for task in [rt.task, *rt.pending_cuts.values()]:
                if task and not task.done():
                    task.cancel()
        await self._store.async_save(self._data_to_store())
        await super().async_shutdown()

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
        """Activity a plain "on" starts: the last one, else the first."""
        activities = self.rooms.get(room_id, {}).get(CONF_ACTIVITIES, {})
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

        Repeating the command that is already running just waits for it.
        """
        rt = self.runtime(room_id)
        running = rt.task if rt.task and not rt.task.done() else None

        if running is not None and rt.command == command:
            await self._await_task(running)
            return
        if running is not None:
            _LOGGER.info("Room '%s': cancelling running %s", room_id, rt.command[0])
            running.cancel()

        async with rt.lock:
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
        persistent_notification.async_dismiss(self.hass, self._notification_id(room_id))
        self._changed()

        needed_switches = self._power_switches(devices, new_devices)
        for switch in needed_switches:
            self._cancel_cut(rt, switch)

        hook: asyncio.Task | None = None
        try:
            if previous is not None:
                await self._async_switch_off_unused(room_id, previous, new_devices, context)

            if needed_switches:
                await self._async_call(
                    "homeassistant",
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: needed_switches},
                    context,
                    f"power on {', '.join(needed_switches)}",
                )

            hook = self._start_hook(room_id, activity_id, CONF_ON_START, context)

            done = 0
            for device_id in new_devices:
                device = devices[device_id]
                if device.get(CONF_READY):
                    await self._async_wait_ready(
                        device[CONF_ENTITY_ID], device[CONF_READY], f"device '{device_id}'"
                    )
                if self._is_off(device[CONF_ENTITY_ID]):
                    await self._async_power_on(device[CONF_ENTITY_ID], context)
                    if device[CONF_DELAY_AFTER_ON]:
                        await self._async_sleep(device[CONF_DELAY_AFTER_ON])
                done += 1
                rt.progress = (done, total)
                self.async_update_listeners()

            for idx, step in enumerate(steps, 1):
                _LOGGER.debug("Room '%s': step %d/%d %s", room_id, idx, len(steps), step)
                await self._async_execute_step(room, step, context)
                if step[CONF_DELAY_AFTER]:
                    await self._async_sleep(step[CONF_DELAY_AFTER])
                done += 1
                rt.progress = (done, total)
                self.async_update_listeners()

            if hook is not None:
                await hook
        except ActivityAborted as err:
            if hook is not None:
                hook.cancel()
            rt.state = ACTIVITY_STATE_ERROR
            rt.error = str(err)
            _LOGGER.error("Room '%s': start of '%s' aborted: %s", room_id, activity_id, err)
            persistent_notification.async_create(
                self.hass,
                f"Start of **{self.activity_name(room_id, activity_id)}** "
                f"aborted: {err}",
                title=f"AV Scenes: {room.get(CONF_NAME, room_id)}",
                notification_id=self._notification_id(room_id),
            )
            self._changed()
            return
        except asyncio.CancelledError:
            if hook is not None:
                hook.cancel()
            raise

        rt.state = ACTIVITY_STATE_ACTIVE
        rt.last_activity = activity_id
        rt.progress = (total, total)
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
        for device_id in unused:
            device = devices[device_id]
            await self._async_power_off(device[CONF_ENTITY_ID], context)
            switch = device.get(CONF_POWER_SWITCH)
            if switch:
                cooldown[switch] = max(cooldown.get(switch, 0), device[CONF_DELAY_AFTER_OFF])

        still_needed = set(self._power_switches(devices, new_devices))
        for switch, delay in cooldown.items():
            if switch not in still_needed:
                self._cancel_cut(rt, switch)
                rt.pending_cuts[switch] = self.hass.async_create_background_task(
                    self._async_cut_later(rt, switch, delay),
                    f"{DOMAIN} {room_id} cut {switch}",
                )

    async def _async_cut_later(self, rt: RoomRuntime, switch: str, delay: float) -> None:
        if delay:
            _LOGGER.debug("Cutting power of %s in %s s", switch, delay)
            await self._async_sleep(delay)
        rt.pending_cuts.pop(switch, None)
        with contextlib.suppress(ActivityAborted):
            await self._async_call(
                "homeassistant",
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: switch},
                Context(),
                f"power off {switch}",
            )

    @staticmethod
    def _cancel_cut(rt: RoomRuntime, switch: str) -> None:
        task = rt.pending_cuts.pop(switch, None)
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
                for device_id in reversed(device_ids):
                    device = devices[device_id]
                    entity_id = device[CONF_ENTITY_ID]
                    delay = device[CONF_DELAY_AFTER_OFF]
                    if self._is_off(entity_id):
                        delay = self._remaining_cooldown(entity_id, delay)
                    else:
                        await self._async_power_off(entity_id, context)
                    if delay > 0:
                        _LOGGER.debug("Waiting %s s after switching off %s", delay, entity_id)
                        await self._async_sleep(delay)

                switches = self._power_switches(devices, device_ids)
                for switch in switches:
                    self._cancel_cut(rt, switch)
                if switches:
                    with contextlib.suppress(ActivityAborted):
                        await self._async_call(
                            "homeassistant",
                            SERVICE_TURN_OFF,
                            {ATTR_ENTITY_ID: list(reversed(switches))},
                            context,
                            f"power off {', '.join(switches)}",
                        )
                if hook is not None:
                    await hook
            except asyncio.CancelledError:
                if hook is not None:
                    hook.cancel()
                raise

        rt.activity = None
        rt.state = ACTIVITY_STATE_IDLE
        rt.error = None
        rt.progress = (0, 0)
        persistent_notification.async_dismiss(self.hass, self._notification_id(room_id))
        self._changed()
        _LOGGER.info("Room '%s': '%s' stopped", room_id, activity_id)

    async def _async_sleep(self, seconds: float) -> None:
        """Wait between actions (a seam for tests)."""
        await asyncio.sleep(seconds)

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

    def _is_available(self, entity_id: str) -> bool:
        state = self.hass.states.get(entity_id)
        return state is not None and state.state != STATE_UNAVAILABLE

    async def _async_wait_ready(
        self, entity_id: str, options: dict[str, Any], label: str
    ) -> bool:
        """Wait until an entity exists and is not unavailable.

        Returns False on a timeout with ``on_timeout: continue`` and raises
        ActivityAborted on a timeout with ``on_timeout: abort``.
        """
        if self._is_available(entity_id):
            return True

        timeout: float = options[CONF_TIMEOUT]
        loop = asyncio.get_running_loop()
        ready: asyncio.Future[None] = loop.create_future()

        @callback
        def _state_changed(event: Event[EventStateChangedData]) -> None:
            new_state = event.data["new_state"]
            if (
                new_state is not None
                and new_state.state != STATE_UNAVAILABLE
                and not ready.done()
            ):
                ready.set_result(None)

        unsub: CALLBACK_TYPE = async_track_state_change_event(
            self.hass, [entity_id], _state_changed
        )
        try:
            if options[CONF_RELOAD_INTEGRATION]:
                self._reload_integration_of(entity_id)
            # The entity may have come up between the first check and subscribing
            if self._is_available(entity_id):
                return True
            _LOGGER.info("Waiting up to %s s for %s to become available", timeout, entity_id)
            try:
                async with asyncio.timeout(timeout):
                    await ready
            except TimeoutError:
                message = f"{label}: {entity_id} not available after {timeout:g} s"
                if options[CONF_ON_TIMEOUT] == ON_TIMEOUT_ABORT:
                    raise ActivityAborted(message) from None
                _LOGGER.warning("%s, continuing", message)
                return False
            _LOGGER.info("%s is available", entity_id)
            return True
        finally:
            # A started reload is left to finish on its own
            unsub()

    def _reload_integration_of(self, entity_id: str) -> asyncio.Task | None:
        """Reload the config entry that provides an entity, once.

        Resets the back-off of an entry in setup_retry. The registry keeps the
        entry even while the entity has no state.
        """
        entity = er.async_get(self.hass).async_get(entity_id)
        if entity is None or entity.config_entry_id is None:
            _LOGGER.warning("Cannot reload integration of %s: not in the entity registry", entity_id)
            return None
        entry_id = entity.config_entry_id
        _LOGGER.info("Reloading config entry %s to bring up %s", entry_id, entity_id)

        async def _reload() -> None:
            try:
                await self.hass.config_entries.async_reload(entry_id)
            except Exception:  # noqa: BLE001 - only logged, the wait decides
                _LOGGER.exception("Reloading config entry %s failed", entry_id)

        return self.hass.async_create_background_task(
            _reload(), f"{DOMAIN} reload {entry_id}"
        )

    # ------------------------------------------------------------------
    # Steps and service calls
    # ------------------------------------------------------------------

    async def _async_execute_step(
        self, room: dict[str, Any], step: dict[str, Any], context: Context
    ) -> None:
        step_type = step[CONF_TYPE]
        entity_id = None
        if CONF_DEVICE in step:
            entity_id = room[CONF_DEVICES][step[CONF_DEVICE]][CONF_ENTITY_ID]

        if step_type == STEP_TYPE_DELAY:
            return
        if step_type == STEP_TYPE_WAIT_AVAILABLE:
            await self._async_wait_ready(
                entity_id or step[CONF_ENTITY_ID], step, f"step {step.get('id', '')}".strip()
            )
            return
        if step_type == STEP_TYPE_POWER_ON:
            await self._async_power_on(entity_id, context)
            return
        if step_type == STEP_TYPE_POWER_OFF:
            await self._async_power_off(entity_id, context)
            return

        call = self._service_for_step(step_type, step, entity_id)
        if call is None:
            return
        domain, service, data, target = call
        await self._async_call(domain, service, data, context, step_type, target)

    @staticmethod
    def _service_for_step(
        step_type: str, step: dict[str, Any], entity_id: str | None
    ) -> tuple[str, str, dict[str, Any], dict[str, Any] | None] | None:
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

    def _is_off(self, entity_id: str) -> bool:
        state = self.hass.states.get(entity_id)
        return state is None or state.state in _OFF_STATES

    async def _async_power_on(self, entity_id: str, context: Context) -> None:
        if entity_id.startswith("cover."):
            await self._async_call(
                "cover", "open_cover", {ATTR_ENTITY_ID: entity_id}, context, "open"
            )
        else:
            await self._async_call(
                "homeassistant", SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, context, "turn on"
            )

    async def _async_power_off(self, entity_id: str, context: Context) -> None:
        if entity_id.startswith("cover."):
            await self._async_call(
                "cover", "close_cover", {ATTR_ENTITY_ID: entity_id}, context, "close"
            )
        else:
            await self._async_call(
                "homeassistant", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, context, "turn off"
            )

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

    @staticmethod
    def _power_switches(devices: dict[str, Any], device_ids: list[str]) -> list[str]:
        """Power switches of the given devices, in order, without duplicates."""
        switches: list[str] = []
        for device_id in device_ids:
            switch = devices[device_id].get(CONF_POWER_SWITCH)
            if switch and switch not in switches:
                switches.append(switch)
        return switches

    def _notification_id(self, room_id: str) -> str:
        return f"{DOMAIN}_{self.entry.entry_id}_{room_id}"
