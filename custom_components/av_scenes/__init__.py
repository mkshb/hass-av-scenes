"""The AV Scenes integration."""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from . import websocket
from .card_resource import async_register_card_resource, async_remove_card_resource
from .const import (
    ATTR_ACTIVITY,
    ATTR_COMMAND,
    ATTR_DEVICE,
    ATTR_ROOM,
    ATTR_VALUE,
    CARD_FILENAME,
    PANEL_FILENAME,
    PANEL_URL_PATH,
    CONF_ROOMS,
    CONFIG_MINOR_VERSION,
    CONFIG_VERSION,
    DOMAIN,
    FRONTEND_URL_BASE,
    SERVICE_RELOAD,
    SERVICE_SEND_COMMAND,
    SERVICE_START_ACTIVITY,
    SERVICE_STOP_ACTIVITY,
    SERVICE_TOGGLE_ACTIVITY,
    SIGNAL_ROOMS_UPDATED,
)
from .coordinator import AVScenesCoordinator
from .migration import migrate_v1_to_v2
from .model import expected_unique_ids

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SCENE, Platform.SWITCH, Platform.SENSOR, Platform.SELECT]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_ROOM_SCHEMA = vol.Schema({vol.Required(ATTR_ROOM): cv.string})
_ACTIVITY_SCHEMA = _ROOM_SCHEMA.extend({vol.Optional(ATTR_ACTIVITY): cv.string})
_START_SCHEMA = _ROOM_SCHEMA.extend({vol.Required(ATTR_ACTIVITY): cv.string})
_SEND_COMMAND_SCHEMA = _ROOM_SCHEMA.extend(
    {
        vol.Required(ATTR_COMMAND): cv.string,
        vol.Optional(ATTR_VALUE): vol.Any(vol.Coerce(float), cv.string),
        vol.Optional(ATTR_DEVICE): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the services, the websocket API and the remote control card."""
    _register_services(hass)
    websocket.async_register(hass)
    await _async_register_frontend(hass)
    return True


def _coordinator_for_room(hass: HomeAssistant, room_id: str) -> AVScenesCoordinator:
    """Find the coordinator that manages a room, or raise."""
    coordinator = websocket.find_room(hass, room_id)
    if coordinator is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_room",
            translation_placeholders={"room": room_id},
        )
    return coordinator


def _register_services(hass: HomeAssistant) -> None:
    """Register the domain services."""

    async def handle_start_activity(call: ServiceCall) -> None:
        room_id = call.data[ATTR_ROOM]
        coordinator = _coordinator_for_room(hass, room_id)
        activity = call.data[ATTR_ACTIVITY]
        if coordinator.resolve_activity(room_id, activity) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_activity",
                translation_placeholders={"room": room_id, "activity": activity},
            )
        await coordinator.async_start_activity(room_id, activity)

    async def handle_stop_activity(call: ServiceCall) -> None:
        room_id = call.data[ATTR_ROOM]
        await _coordinator_for_room(hass, room_id).async_stop_activity(room_id)

    async def handle_toggle_activity(call: ServiceCall) -> None:
        room_id = call.data[ATTR_ROOM]
        await _coordinator_for_room(hass, room_id).async_toggle_activity(
            room_id, call.data.get(ATTR_ACTIVITY)
        )

    async def handle_send_command(call: ServiceCall) -> None:
        room_id = call.data[ATTR_ROOM]
        await _coordinator_for_room(hass, room_id).async_send_command(
            room_id,
            call.data[ATTR_COMMAND],
            value=call.data.get(ATTR_VALUE),
            device_id=call.data.get(ATTR_DEVICE),
            context=call.context,
        )

    async def handle_reload(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is ConfigEntryState.LOADED:
                await hass.config_entries.async_reload(entry.entry_id)

    hass.services.async_register(
        DOMAIN, SERVICE_START_ACTIVITY, handle_start_activity, schema=_START_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_ACTIVITY, handle_stop_activity, schema=_ROOM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE_ACTIVITY, handle_toggle_activity, schema=_ACTIVITY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_COMMAND, handle_send_command, schema=_SEND_COMMAND_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_RELOAD, handle_reload)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the remote control card and the configuration panel.

    The card is a dashboard resource (see card_resource.py), or with
    resources in YAML a module loaded on every page; the panel is shown to
    admins in the sidebar. Both are built by the release workflow; a plain
    checkout has none.
    """
    directory = Path(__file__).parent / "frontend"

    def _mtimes() -> dict[str, int]:
        return {
            name: int((directory / name).stat().st_mtime)
            for name in (CARD_FILENAME, PANEL_FILENAME)
            if (directory / name).is_file()
        }

    mtimes = await hass.async_add_executor_job(_mtimes)
    if CARD_FILENAME not in mtimes:
        _LOGGER.warning("Frontend not found in %s; build it first", directory)
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL_BASE, str(directory), cache_headers=False)]
    )
    if "frontend" not in hass.config.components:
        return
    # Imported late: the frontend is only an after-dependency
    from homeassistant.components import panel_custom
    from homeassistant.components.frontend import add_extra_js_url

    version = (await async_get_integration(hass, DOMAIN)).version

    def url(name: str) -> str:
        return f"{FRONTEND_URL_BASE}/{name}?v={version}-{mtimes[name]}"

    card_url = url(CARD_FILENAME)
    if not await async_register_card_resource(hass, _card_base(), card_url):
        add_extra_js_url(hass, card_url)
    if PANEL_FILENAME in mtimes:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name="av-scenes-panel",
            sidebar_title="AV Scenes",
            sidebar_icon="mdi:remote-tv",
            module_url=url(PANEL_FILENAME),
            require_admin=True,
            config_panel_domain=DOMAIN,
        )


def _card_base() -> str:
    """URL of the card without the version."""
    return f"{FRONTEND_URL_BASE}/{CARD_FILENAME}"


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
    _async_remove_stale(hass, entry, coordinator.rooms)
    async_dispatcher_send(hass, SIGNAL_ROOMS_UPDATED)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


@callback
def _async_remove_stale(hass: HomeAssistant, entry: ConfigEntry, rooms: dict) -> None:
    """Remove entities and devices of activities and rooms that are gone.

    Home Assistant keeps registry entries of entities that are no longer
    created; they would stay as "unavailable" forever.
    """
    wanted = expected_unique_ids(rooms)
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.unique_id not in wanted:
            _LOGGER.info("Removing %s, its activity or room no longer exists", entity.entity_id)
            entity_registry.async_remove(entity.entity_id)
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not any(domain == DOMAIN and room in rooms for domain, room in device.identifiers):
            _LOGGER.info("Removing device %s, its room no longer exists", device.name)
            device_registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading AV Scenes integration")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: AVScenesCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
        async_dispatcher_send(hass, SIGNAL_ROOMS_UPDATED)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the card's dashboard resource with the last entry."""
    if not hass.config_entries.async_entries(DOMAIN):
        await async_remove_card_resource(hass, _card_base())


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
