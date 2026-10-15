"""The AV Scenes integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONFIG_MINOR_VERSION,
    CONFIG_VERSION,
    CONF_ROOMS,
    DOMAIN,
    SERVICE_START_ACTIVITY,
    SERVICE_STOP_ACTIVITY,
    SERVICE_RELOAD,
    SERVICE_TOGGLE_ACTIVITY,
    ATTR_ROOM,
    ATTR_ACTIVITY,
)
from .coordinator import AVScenesCoordinator
from .migration import migrate_v1_to_v2

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

    async def handle_toggle_activity(call: ServiceCall) -> None:
        room_id = call.data.get(ATTR_ROOM)
        coordinator = _get_coordinator_for_room(hass, room_id)
        if coordinator is None:
            _LOGGER.error("No coordinator found for room '%s'", room_id)
            return
        await coordinator.async_toggle_activity(room_id, call.data.get(ATTR_ACTIVITY))

    async def handle_reload(call: ServiceCall) -> None:
        for entry_id, coordinator in list(hass.data.get(DOMAIN, {}).items()):
            if isinstance(coordinator, AVScenesCoordinator):
                await hass.config_entries.async_reload(entry_id)

    hass.services.async_register(DOMAIN, SERVICE_START_ACTIVITY, handle_start_activity)
    hass.services.async_register(DOMAIN, SERVICE_STOP_ACTIVITY, handle_stop_activity)
    hass.services.async_register(DOMAIN, SERVICE_TOGGLE_ACTIVITY, handle_toggle_activity)
    hass.services.async_register(DOMAIN, SERVICE_RELOAD, handle_reload)
    _LOGGER.debug("Domain services registered")


def _unregister_services(hass: HomeAssistant) -> None:
    """Unregister domain-level services (called when last entry is removed)."""
    hass.services.async_remove(DOMAIN, SERVICE_START_ACTIVITY)
    hass.services.async_remove(DOMAIN, SERVICE_STOP_ACTIVITY)
    hass.services.async_remove(DOMAIN, SERVICE_TOGGLE_ACTIVITY)
    hass.services.async_remove(DOMAIN, SERVICE_RELOAD)
    _LOGGER.debug("Domain services unregistered")


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry to the current schema."""
    if entry.version > CONFIG_VERSION:
        # Downgrade from a newer release: refuse instead of guessing
        _LOGGER.error(
            "Config entry version %s is newer than supported version %s",
            entry.version,
            CONFIG_VERSION,
        )
        return False

    if entry.version == 1:
        _LOGGER.info("Migrating AV Scenes config entry from version 1 to 2")
        hass.config_entries.async_update_entry(
            entry,
            data=migrate_v1_to_v2(dict(entry.data)),
            version=2,
            minor_version=CONFIG_MINOR_VERSION,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AV Scenes from a config entry."""
    _LOGGER.debug("Setting up AV Scenes integration")

    hass.data.setdefault(DOMAIN, {})

    coordinator = AVScenesCoordinator(hass, entry)
    # Raises ConfigEntryError on an invalid configuration
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services once for the whole domain
    if not hass.services.has_service(DOMAIN, SERVICE_START_ACTIVITY):
        _register_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading AV Scenes integration")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: AVScenesCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

        # Unregister services when the last entry is removed
        remaining = [v for v in hass.data[DOMAIN].values() if isinstance(v, AVScenesCoordinator)]
        if not remaining:
            _unregister_services(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply a changed configuration.

    As long as no room or activity was added, removed or renamed, the entities
    stay the same and the new configuration is applied in place, so running
    activities are not interrupted. Otherwise the entry is reloaded.
    """
    coordinator: AVScenesCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is not None and coordinator.entity_layout(
        entry.data.get(CONF_ROOMS) or {}
    ) == coordinator.entity_layout(coordinator.rooms):
        _LOGGER.debug("Applying the changed configuration without reload")
        await coordinator.async_refresh()
        if coordinator.last_update_success:
            return
    await hass.config_entries.async_reload(entry.entry_id)
