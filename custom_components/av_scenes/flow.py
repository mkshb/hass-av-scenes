"""The flow of an activity: what a start or stop switches, when and how.

The configuration panel shows it next to the activity, computed from the
configuration being edited. It follows the engine in coordinator.py step by
step; the tests run both and compare them.

A flow is a list of rows. Every row has a ``kind`` and ``at``, the earliest
and latest time in seconds after the command at which the row begins. Only
the configured waits count; how long devices take to answer is not known.

What depends on the state of the house at that moment carries a
``condition``: ``outlet_was_off`` (its outlet was switched on by this start),
``if_off`` (the device is off), ``if_on`` (the device is on) and
``if_not_ready`` (the readiness check is not met yet).
"""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACTIVITIES,
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
    CONF_POWER_SWITCH,
    CONF_READY,
    CONF_RELOAD_INTEGRATION,
    CONF_STATE,
    CONF_STEPS,
    CONF_TIMEOUT,
    CONF_TYPE,
    STEP_TYPE_DELAY,
    STEP_TYPE_POWER_OFF,
    STEP_TYPE_POWER_ON,
    STEP_TYPE_WAIT_AVAILABLE,
)
from .control import action_names
from .coordinator import can_switch, power_service, power_switches, step_service
from .model import CONF_DELAY_AFTER


class _Clock:
    """Earliest and latest time since the command, from the configured waits."""

    def __init__(self) -> None:
        self.min = 0.0
        self.max = 0.0

    def wait(self, seconds: float) -> None:
        self.min += seconds
        self.max += seconds

    def wait_up_to(self, seconds: float) -> None:
        self.max += seconds

    def not_before(self, seconds: float) -> None:
        self.min = max(self.min, seconds)
        self.max = max(self.max, seconds)

    @property
    def at(self) -> list[float]:
        return [round(self.min, 1), round(self.max, 1)]


def shared_outlets(
    room_id: str, room: dict[str, Any], others: dict[str, dict[str, Any]]
) -> dict[str, list[str]]:
    """Outlet -> names of the other rooms that have a device on it."""
    outlets = {d.get(CONF_POWER_SWITCH) for d in room[CONF_DEVICES].values()} - {None}
    shared: dict[str, list[str]] = {}
    for other_id, other in others.items():
        if other_id == room_id or not isinstance(other, dict):
            continue
        for device in (other.get(CONF_DEVICES) or {}).values():
            outlet = device.get(CONF_POWER_SWITCH) if isinstance(device, dict) else None
            if outlet in outlets:
                names = shared.setdefault(outlet, [])
                name = other.get(CONF_NAME) or other_id
                if name not in names:
                    names.append(name)
    return shared


def _action(domain_service: tuple[str, str]) -> str:
    return ".".join(domain_service)


def _switch_row(
    hass: HomeAssistant, kind: str, device_id: str, entity_id: str, at: list[float], **extra: Any
) -> dict[str, Any]:
    on = kind == "turn_on"
    row: dict[str, Any] = {"kind": kind, "at": at, "device": device_id, "entity_id": entity_id}
    if can_switch(hass, entity_id, on=on):
        row["action"] = _action(power_service(entity_id, on=on))
    else:
        row["skip"] = "cannot_switch"
    row.update(extra)
    return row


def _hook(activity: dict[str, Any], key: str, at: list[float]) -> dict[str, Any] | None:
    actions = activity.get(key) or []
    if not actions:
        return None
    return {"kind": "hook", "at": at, "hook": key, "actions": action_names(actions)}


def _ready_row(entity_id: str, options: dict[str, Any], at: list[float], **extra: Any) -> dict[str, Any]:
    return {
        "kind": "ready",
        "at": at,
        "entity_id": options.get(CONF_ENTITY_ID) or entity_id,
        "states": options.get(CONF_STATE),
        "timeout": options[CONF_TIMEOUT],
        "on_timeout": options[CONF_ON_TIMEOUT],
        **extra,
    }


def plan_start(
    hass: HomeAssistant,
    room_id: str,
    room: dict[str, Any],
    activity_id: str,
    previous: str | None = None,
    others: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Rows of starting an activity, from idle or from another activity.

    From idle, every device and outlet is taken as off. Switching assumes
    the previous activity runs completely: its devices and outlets are on.
    """
    devices: dict[str, Any] = room[CONF_DEVICES]
    activity = room[CONF_ACTIVITIES][activity_id]
    new_devices: list[str] = activity[CONF_DEVICES]
    old_devices: list[str] = (
        room[CONF_ACTIVITIES][previous][CONF_DEVICES]
        if previous is not None and previous != activity_id
        else []
    )
    shared = shared_outlets(room_id, room, others or {})
    clock = _Clock()
    rows: list[dict[str, Any]] = [{"kind": "state", "at": clock.at, "state": "starting"}]

    # Smart switching
    needed = power_switches(devices, new_devices)
    unused = [d for d in reversed(old_devices) if d not in new_devices]
    cooldown: dict[str, float] = {}
    for device_id in unused:
        device = devices[device_id]
        rows.append(
            _switch_row(
                hass, "turn_off", device_id, device[CONF_ENTITY_ID], clock.at, reason="unused"
            )
        )
        if switch := device.get(CONF_POWER_SWITCH):
            cooldown[switch] = max(cooldown.get(switch, 0), device[CONF_DELAY_AFTER_OFF])
    cuts = [(s, delay) for s, delay in cooldown.items() if s not in needed]
    for switch in cooldown:
        if switch in needed:
            rows.append({"kind": "outlet_keep", "at": clock.at, "entity_id": switch, "reason": "needed"})

    # Power
    was_on = set(power_switches(devices, old_devices))
    powered = [s for s in needed if s not in was_on]
    if needed:
        rows.append(
            {
                "kind": "outlets_on",
                "at": clock.at,
                "action": "homeassistant.turn_on",
                "entities": needed,
                "already_on": [s for s in needed if s in was_on],
            }
        )
    if hook := _hook(activity, CONF_ON_START, clock.at):
        rows.append(hook)

    # Devices
    for index, device_id in enumerate(new_devices, 1):
        device = devices[device_id]
        entity_id = device[CONF_ENTITY_ID]
        rows.append(
            {"kind": "device", "at": clock.at, "device": device_id, "entity_id": entity_id, "index": index}
        )
        if device_id in old_devices:
            rows.append({"kind": "already_on", "at": clock.at, "device": device_id, "previous": previous})
            continue
        fresh_power = device.get(CONF_POWER_SWITCH) in powered
        condition = None if previous else "outlet_was_off"
        if fresh_power and device[CONF_DELAY_AFTER_POWER]:
            rows.append(
                {
                    "kind": "boot",
                    "at": clock.at,
                    "device": device_id,
                    "seconds": device[CONF_DELAY_AFTER_POWER],
                    "outlet": device[CONF_POWER_SWITCH],
                    "condition": condition,
                }
            )
            clock.not_before(device[CONF_DELAY_AFTER_POWER])
        if ready := device.get(CONF_READY):
            checked = ready.get(CONF_ENTITY_ID) or entity_id
            if fresh_power and ready[CONF_RELOAD_INTEGRATION]:
                rows.append(
                    {"kind": "reload", "at": clock.at, "entity_id": checked, "condition": condition}
                )
                reload = False
            else:
                reload = ready[CONF_RELOAD_INTEGRATION]
            rows.append(_ready_row(entity_id, ready, clock.at, device=device_id, reload=reload))
            clock.wait_up_to(ready[CONF_TIMEOUT])
        rows.append(_switch_row(hass, "turn_on", device_id, entity_id, clock.at, condition="if_off"))
        if device[CONF_DELAY_AFTER_ON]:
            rows.append(
                {
                    "kind": "wait",
                    "at": clock.at,
                    "seconds": device[CONF_DELAY_AFTER_ON],
                    "reason": "delay_after_on",
                    "condition": "if_off",
                }
            )
            clock.wait(device[CONF_DELAY_AFTER_ON])

    # Steps
    rows.extend(_step_rows(hass, room, activity, clock))

    if hook is not None:
        rows.append({"kind": "hook_wait", "at": clock.at, "hook": CONF_ON_START})
    rows.append({"kind": "state", "at": clock.at, "state": "active"})
    done = clock.at

    # Outlets of the previous activity cut in the background
    for switch, delay in cuts:
        row: dict[str, Any] = {
            "kind": "outlets_off",
            "at": [delay, delay],
            "action": "homeassistant.turn_off",
            "entities": [switch],
            "background": True,
        }
        if switch in shared:
            row["unless_rooms"] = shared[switch]
        rows.append(row)

    return {"rows": rows, "done": done}


def _step_rows(
    hass: HomeAssistant, room: dict[str, Any], activity: dict[str, Any], clock: _Clock
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = activity[CONF_STEPS]
    if steps:
        rows.append({"kind": "steps", "at": clock.at, "count": len(steps)})
    for index, step in enumerate(steps, 1):
        step_type = step[CONF_TYPE]
        device_id = step.get(CONF_DEVICE)
        entity_id = room[CONF_DEVICES][device_id][CONF_ENTITY_ID] if device_id else None
        base = {"step": index, "step_type": step_type}
        if step_type == STEP_TYPE_WAIT_AVAILABLE:
            rows.append(
                _ready_row(
                    entity_id or step[CONF_ENTITY_ID],
                    step,
                    clock.at,
                    device=device_id,
                    reload=step[CONF_RELOAD_INTEGRATION],
                    **base,
                )
            )
            clock.wait_up_to(step[CONF_TIMEOUT])
        elif step_type in (STEP_TYPE_POWER_ON, STEP_TYPE_POWER_OFF):
            kind = "turn_on" if step_type == STEP_TYPE_POWER_ON else "turn_off"
            rows.append(_switch_row(hass, kind, device_id, entity_id, clock.at, **base))
        elif step_type != STEP_TYPE_DELAY:
            call = step_service(step_type, step, entity_id)
            if call is not None:
                domain, service, data, target = call
                rows.append(
                    {
                        "kind": "step",
                        "at": clock.at,
                        "device": device_id,
                        "entity_id": entity_id,
                        "action": f"{domain}.{service}",
                        "data": data,
                        "target": None if entity_id else target,
                        **base,
                    }
                )
        if step[CONF_DELAY_AFTER]:
            rows.append(
                {
                    "kind": "wait",
                    "at": clock.at,
                    "seconds": step[CONF_DELAY_AFTER],
                    "reason": "delay_after",
                    **base,
                }
            )
            clock.wait(step[CONF_DELAY_AFTER])
    return rows


def plan_stop(
    hass: HomeAssistant,
    room_id: str,
    room: dict[str, Any],
    activity_id: str,
    others: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Rows of stopping an activity that runs completely."""
    devices: dict[str, Any] = room[CONF_DEVICES]
    activity = room[CONF_ACTIVITIES][activity_id]
    device_ids: list[str] = activity[CONF_DEVICES]
    shared = shared_outlets(room_id, room, others or {})
    clock = _Clock()
    rows: list[dict[str, Any]] = [{"kind": "state", "at": clock.at, "state": "stopping"}]
    if hook := _hook(activity, CONF_ON_STOP, clock.at):
        rows.append(hook)

    cooldown: dict[str, float] = {}
    for device_id in reversed(device_ids):
        device = devices[device_id]
        rows.append(
            _switch_row(
                hass,
                "turn_off",
                device_id,
                device[CONF_ENTITY_ID],
                clock.at,
                condition="if_on",
                cooldown=device[CONF_DELAY_AFTER_OFF],
            )
        )
        if switch := device.get(CONF_POWER_SWITCH):
            cooldown[switch] = max(cooldown.get(switch, 0.0), device[CONF_DELAY_AFTER_OFF])

    switches = list(reversed(power_switches(devices, device_ids)))
    now = [s for s in switches if cooldown.get(s, 0) <= 0]
    if now:
        row: dict[str, Any] = {
            "kind": "outlets_off",
            "at": clock.at,
            "action": "homeassistant.turn_off",
            "entities": now,
        }
        if kept := {s: shared[s] for s in now if s in shared}:
            row["unless_rooms"] = sorted({name for names in kept.values() for name in names})
        rows.append(row)
    if hook is not None:
        rows.append({"kind": "hook_wait", "at": clock.at, "hook": CONF_ON_STOP})
    rows.append({"kind": "state", "at": clock.at, "state": "idle"})
    done = clock.at

    for switch in switches:
        if switch in now:
            continue
        delay = cooldown[switch]
        row = {
            "kind": "outlets_off",
            "at": [delay, delay],
            "action": "homeassistant.turn_off",
            "entities": [switch],
            "background": True,
        }
        if switch in shared:
            row["unless_rooms"] = shared[switch]
        rows.append(row)

    return {"rows": rows, "done": done}
