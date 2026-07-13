"""Tests for the AV Scenes coordinator's activity logic."""
import uuid

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.av_scenes.const import (
    DOMAIN,
    CONF_ROOMS,
    CONF_ACTIVITIES,
    CONF_STEPS,
    CONF_STEP_ID,
    CONF_STEP_TYPE,
    CONF_ENTITY_ID,
    CONF_STEP_DELAY_AFTER,
    CONF_STEP_PARAMETERS,
    STEP_TYPE_POWER_ON,
    STEP_TYPE_CALL_ACTION,
    ACTIVITY_STATE_ACTIVE,
    ACTIVITY_STATE_ERROR,
    ACTIVITY_STATE_IDLE,
)
from custom_components.av_scenes.coordinator import AVScenesCoordinator

RECEIVER = "media_player.receiver"
PROJECTOR = "switch.projector"
APPLETV = "media_player.appletv"
SONOS = "media_player.sonos"


def _step(step_type: str, entity_id: str = "", delay_after: int = 0, **params) -> dict:
    return {
        CONF_STEP_ID: str(uuid.uuid4()),
        CONF_STEP_TYPE: step_type,
        CONF_ENTITY_ID: entity_id,
        CONF_STEP_DELAY_AFTER: delay_after,
        CONF_STEP_PARAMETERS: params,
    }


def _power_on(entity_id: str) -> dict:
    return _step(STEP_TYPE_POWER_ON, entity_id)


def _rooms() -> dict:
    return {
        CONF_ROOMS: {
            "living": {
                "name": "Living",
                CONF_ACTIVITIES: {
                    "AppleTV": {
                        CONF_STEPS: [
                            _power_on(RECEIVER),
                            _power_on(PROJECTOR),
                            _power_on(APPLETV),
                        ]
                    },
                    "Sonos": {
                        CONF_STEPS: [
                            _power_on(RECEIVER),
                            _power_on(SONOS),
                        ]
                    },
                    "Broken": {
                        CONF_STEPS: [
                            _step(STEP_TYPE_CALL_ACTION, action="nonexistent.service"),
                        ]
                    },
                },
            }
        }
    }


async def _make_coordinator(hass: HomeAssistant) -> AVScenesCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, data=_rooms())
    entry.add_to_hass(hass)
    coordinator = AVScenesCoordinator(hass, entry)
    await coordinator.async_refresh()
    return coordinator


async def test_start_activity_powers_on_all_devices(hass: HomeAssistant):
    """Starting an activity powers on every device and reports active."""
    coordinator = await _make_coordinator(hass)
    turn_on = async_mock_service(hass, "homeassistant", "turn_on")

    await coordinator.async_start_activity("living", "AppleTV")
    await hass.async_block_till_done()

    powered = {c.data[ATTR_ENTITY_ID] for c in turn_on}
    assert powered == {RECEIVER, PROJECTOR, APPLETV}
    assert coordinator.activity_states["living"] == ACTIVITY_STATE_ACTIVE
    assert coordinator.active_activities["living"] == "AppleTV"


async def test_smart_switching_only_turns_off_unneeded(hass: HomeAssistant):
    """Switching activities turns off devices not used by the new activity."""
    coordinator = await _make_coordinator(hass)
    async_mock_service(hass, "homeassistant", "turn_on")
    turn_off = async_mock_service(hass, "homeassistant", "turn_off")

    await coordinator.async_start_activity("living", "AppleTV")
    await hass.async_block_till_done()
    await coordinator.async_start_activity("living", "Sonos")
    await hass.async_block_till_done()

    turned_off = {c.data[ATTR_ENTITY_ID] for c in turn_off}
    # Projector + Apple TV are no longer needed; the receiver stays on.
    assert turned_off == {PROJECTOR, APPLETV}
    assert coordinator.active_activities["living"] == "Sonos"


async def test_stop_activity_reverses_order(hass: HomeAssistant):
    """Stopping powers devices off in reverse of the start order."""
    coordinator = await _make_coordinator(hass)
    async_mock_service(hass, "homeassistant", "turn_on")
    turn_off = async_mock_service(hass, "homeassistant", "turn_off")

    await coordinator.async_start_activity("living", "AppleTV")
    await hass.async_block_till_done()
    await coordinator.async_stop_activity("living")
    await hass.async_block_till_done()

    order = [c.data[ATTR_ENTITY_ID] for c in turn_off]
    assert order == [APPLETV, PROJECTOR, RECEIVER]
    assert coordinator.activity_states["living"] == ACTIVITY_STATE_IDLE
    assert "living" not in coordinator.active_activities


async def test_all_steps_failing_yields_error_state(hass: HomeAssistant):
    """If every step errors the activity reports 'error', not 'active'."""
    coordinator = await _make_coordinator(hass)

    await coordinator.async_start_activity("living", "Broken")
    await hass.async_block_till_done()

    assert coordinator.activity_states["living"] == ACTIVITY_STATE_ERROR
