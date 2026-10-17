"""Select platform for AV Scenes integration.

Provides one SelectEntity per room that:
 - shows the active activity name (or a status label during transitions)
 - lets the user start an activity by selecting its name
 - lets the user stop the current activity by selecting "idle" (shown as "—")
"""
from __future__ import annotations

from collections import Counter
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_ACTIVITIES,
    ACTIVITY_STATE_IDLE,
    ACTIVITY_STATE_STARTING,
    ACTIVITY_STATE_STOPPING,
    ACTIVITY_STATE_ERROR,
)
from .coordinator import AVScenesCoordinator
from .model import select_unique_id

_LOGGER = logging.getLogger(__name__)

# Fixed options for idle and the transitional states; their labels come from
# the state translations (entity.select.scene.state). Activities are listed by
# their display name, which is not translated.
_OPT_IDLE = ACTIVITY_STATE_IDLE
_OPT_STARTING = ACTIVITY_STATE_STARTING
_OPT_STOPPING = ACTIVITY_STATE_STOPPING
_OPT_ERROR = ACTIVITY_STATE_ERROR

# Options the user must not be able to actively choose
_READONLY_OPTIONS = {_OPT_STARTING, _OPT_STOPPING, _OPT_ERROR}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AV Scenes select entities from a config entry."""
    coordinator: AVScenesCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        RoomActivitySelect(coordinator, room_id)
        for room_id in coordinator.rooms
    ]
    async_add_entities(entities)
    _LOGGER.debug("Created %d room activity selects", len(entities))


class RoomActivitySelect(CoordinatorEntity, SelectEntity):
    """Select entity that shows the current activity and allows switching."""

    _attr_has_entity_name = True
    _attr_translation_key = "scene"
    _attr_icon = "mdi:play-circle-outline"

    def __init__(self, coordinator: AVScenesCoordinator, room_id: str) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.room_id = room_id

        self._attr_unique_id = select_unique_id(room_id)

    # ------------------------------------------------------------------
    # Options — activity names + idle; transitional states added live
    # ------------------------------------------------------------------

    def _activity_options(self) -> dict[str, str]:
        """Option -> activity ID, in display order.

        An option is the activity's display name. A name that several
        activities share, or that is one of the fixed options (idle,
        starting, ...), gets the activity ID added, so every option starts
        exactly one activity.
        """
        activities = self.coordinator.rooms.get(self.room_id, {}).get(CONF_ACTIVITIES, {})
        names = {a: self.coordinator.activity_name(self.room_id, a) for a in activities}
        taken = Counter(names.values())
        fixed = {_OPT_IDLE, *_READONLY_OPTIONS}
        return {
            (name if taken[name] == 1 and name not in fixed else f"{name} ({activity_id})"): activity_id
            for activity_id, name in names.items()
        }

    @property
    def options(self) -> list[str]:
        """Return all selectable options plus any active status label."""
        base = [_OPT_IDLE, *self._activity_options()]

        state = self.coordinator.activity_states.get(self.room_id, ACTIVITY_STATE_IDLE)
        if state == ACTIVITY_STATE_STARTING:
            return [_OPT_STARTING] + base
        if state == ACTIVITY_STATE_STOPPING:
            return [_OPT_STOPPING] + base
        if state == ACTIVITY_STATE_ERROR:
            return [_OPT_ERROR] + base
        return base

    # ------------------------------------------------------------------
    # Current value
    # ------------------------------------------------------------------

    @property
    def current_option(self) -> str:
        """Return the currently displayed option."""
        state = self.coordinator.activity_states.get(self.room_id, ACTIVITY_STATE_IDLE)

        if state == ACTIVITY_STATE_STARTING:
            return _OPT_STARTING
        if state == ACTIVITY_STATE_STOPPING:
            return _OPT_STOPPING
        if state == ACTIVITY_STATE_ERROR:
            return _OPT_ERROR

        activity = self.coordinator.active_activities.get(self.room_id)
        if not activity:
            return _OPT_IDLE
        return next(
            (option for option, a in self._activity_options().items() if a == activity),
            _OPT_IDLE,
        )

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    async def async_select_option(self, option: str) -> None:
        """Handle user selection."""
        if option in _READONLY_OPTIONS:
            # Transitional states must not be actively selected
            _LOGGER.debug("Ignoring selection of read-only option '%s'", option)
            return

        if option == _OPT_IDLE:
            await self.coordinator.async_stop_activity(self.room_id)
        elif (activity_id := self._activity_options().get(option)) is not None:
            await self.coordinator.async_start_activity(self.room_id, activity_id)

    # ------------------------------------------------------------------
    # Device
    # ------------------------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        """The room's device, in the room's area."""
        return self.coordinator.device_info(self.room_id)

    # ------------------------------------------------------------------

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
