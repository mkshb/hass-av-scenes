"""The AV Scenes integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_START_ACTIVITY,
    SERVICE_STOP_ACTIVITY,
    SERVICE_RELOAD,
    ATTR_ROOM,
    ATTR_ACTIVITY,
)
from .coordinator import AVScenesCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SCENE, Platform.SWITCH, Platform.SENSOR, Platform.SELECT]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _get_coordinator_for_room(hass: HomeAssistant, room_id: str) -> AVScenesCoordinator | None:
    """Find the coordinator that manages the given room."""
    for coordinator in hass.data.get(DOMAIN, {}).values():
        if isinstance(coordinator, AVScenesCoordinator) and room_id in coordinator.rooms:
            return coordinator
    return None


def _register_services(hass: HomeAssistant) -> None:
    """Register domain-level services (called once when first entry is set up)."""

    async def handle_start_activity(call: ServiceCall) -> None:
        room_id = call.data.get(ATTR_ROOM)
        activity_name = call.data.get(ATTR_ACTIVITY)
        coordinator = _get_coordinator_for_room(hass, room_id)
        if coordinator is None:
            _LOGGER.error("No coordinator found for room '%s'", room_id)
            return
        await coordinator.async_start_activity(room_id, activity_name)

    async def handle_stop_activity(call: ServiceCall) -> None:
        room_id = call.data.get(ATTR_ROOM)
        coordinator = _get_coordinator_for_room(hass, room_id)
        if coordinator is None:
            _LOGGER.error("No coordinator found for room '%s'", room_id)
            return
        await coordinator.async_stop_activity(room_id)

    async def handle_reload(call: ServiceCall) -> None:
        for entry_id, coordinator in list(hass.data.get(DOMAIN, {}).items()):
            if isinstance(coordinator, AVScenesCoordinator):
                await hass.config_entries.async_reload(entry_id)

    hass.services.async_register(DOMAIN, SERVICE_START_ACTIVITY, handle_start_activity)
    hass.services.async_register(DOMAIN, SERVICE_STOP_ACTIVITY, handle_stop_activity)
    hass.services.async_register(DOMAIN, SERVICE_RELOAD, handle_reload)
    _LOGGER.debug("Domain services registered")


def _unregister_services(hass: HomeAssistant) -> None:
    """Unregister domain-level services (called when last entry is removed)."""
    hass.services.async_remove(DOMAIN, SERVICE_START_ACTIVITY)
    hass.services.async_remove(DOMAIN, SERVICE_STOP_ACTIVITY)
    hass.services.async_remove(DOMAIN, SERVICE_RELOAD)
    _LOGGER.debug("Domain services unregistered")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AV Scenes from a config entry."""
    _LOGGER.debug("Setting up AV Scenes integration")

    hass.data.setdefault(DOMAIN, {})

    coordinator = AVScenesCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services once for the whole domain
    if not hass.services.has_service(DOMAIN, SERVICE_START_ACTIVITY):
        _register_services(hass)

    # -----------------------------------------------------------------------
    # TEMPORARY DEBUG LOGGING — remove these two lines when no longer needed
    from .debug_log import enable_debug_log  # noqa: PLC0415
    enable_debug_log(hass)
    # -----------------------------------------------------------------------

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading AV Scenes integration")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        # Unregister services when the last entry is removed
        remaining = [v for v in hass.data[DOMAIN].values() if isinstance(v, AVScenesCoordinator)]
        if not remaining:
            _unregister_services(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
