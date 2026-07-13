"""Diagnostics support for the AV Scenes integration."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import AVScenesConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AVScenesConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Exposes the full stored configuration (rooms/activities/steps) plus the
    live runtime state. There are no credentials to redact — step parameters
    only ever hold device settings the user chose in the UI. This makes the
    configuration portable: it can be downloaded and re-applied to another
    instance.
    """
    coordinator = entry.runtime_data
    return {
        "data": dict(entry.data),
        "runtime": {
            "rooms": coordinator.rooms,
            "active_activities": coordinator.active_activities,
            "activity_states": coordinator.activity_states,
        },
    }
