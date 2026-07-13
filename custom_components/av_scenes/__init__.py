"""The AV Scenes integration."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_START_ACTIVITY,
    SERVICE_STOP_ACTIVITY,
    SERVICE_RELOAD,
    ATTR_ROOM,
    ATTR_ACTIVITY,
)
from .coordinator import AVScenesConfigEntry, AVScenesCoordinator

_START_ACTIVITY_SCHEMA = vol.Schema({
    vol.Required(ATTR_ROOM): cv.string,
    vol.Required(ATTR_ACTIVITY): cv.string,
})

_STOP_ACTIVITY_SCHEMA = vol.Schema({
    vol.Required(ATTR_ROOM): cv.string,
})

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SCENE, Platform.SWITCH, Platform.SENSOR, Platform.SELECT]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _loaded_coordinators(hass: HomeAssistant) -> list[AVScenesCoordinator]:
    """Return the coordinators of all currently loaded AV Scenes entries."""
    return [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]


def _get_coordinator_for_room(hass: HomeAssistant, room_id: str) -> AVScenesCoordinator | None:
    """Find the coordinator that manages the given room."""
    for coordinator in _loaded_coordinators(hass):
        if room_id in coordinator.rooms:
            return coordinator
    return None


def _register_services(hass: HomeAssistant) -> None:
    """Register domain-level services (called once when first entry is set up)."""

    async def handle_start_activity(call: ServiceCall) -> None:
        room_id = call.data[ATTR_ROOM]
        activity_name = call.data[ATTR_ACTIVITY]
        coordinator = _get_coordinator_for_room(hass, room_id)
        if coordinator is None:
            raise ServiceValidationError(f"No AV Scenes room found for '{room_id}'")
        await coordinator.async_start_activity(room_id, activity_name)

    async def handle_stop_activity(call: ServiceCall) -> None:
        room_id = call.data[ATTR_ROOM]
        coordinator = _get_coordinator_for_room(hass, room_id)
        if coordinator is None:
            raise ServiceValidationError(f"No AV Scenes room found for '{room_id}'")
        await coordinator.async_stop_activity(room_id)

    async def handle_reload(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is ConfigEntryState.LOADED:
                await hass.config_entries.async_reload(entry.entry_id)

    hass.services.async_register(
        DOMAIN, SERVICE_START_ACTIVITY, handle_start_activity, schema=_START_ACTIVITY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_ACTIVITY, handle_stop_activity, schema=_STOP_ACTIVITY_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_RELOAD, handle_reload)
    _LOGGER.debug("Domain services registered")


def _unregister_services(hass: HomeAssistant) -> None:
    """Unregister domain-level services (called when last entry is removed)."""
    hass.services.async_remove(DOMAIN, SERVICE_START_ACTIVITY)
    hass.services.async_remove(DOMAIN, SERVICE_STOP_ACTIVITY)
    hass.services.async_remove(DOMAIN, SERVICE_RELOAD)
    _LOGGER.debug("Domain services unregistered")


async def async_setup_entry(hass: HomeAssistant, entry: AVScenesConfigEntry) -> bool:
    """Set up AV Scenes from a config entry."""
    _LOGGER.debug("Setting up AV Scenes integration")

    coordinator = AVScenesCoordinator(hass, entry)
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services once for the whole domain
    if not hass.services.has_service(DOMAIN, SERVICE_START_ACTIVITY):
        _register_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AVScenesConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading AV Scenes integration")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and not _loaded_coordinators(hass):
        # No other loaded entries remain — drop the domain-level services.
        # (The entry being unloaded is already out of the LOADED state here.)
        _unregister_services(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: AVScenesConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
