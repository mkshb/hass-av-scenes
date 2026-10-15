"""Shared fixtures for AV Scenes tests."""
import pytest

from homeassistant.core import HomeAssistant

from .common import BEAMER, ONKYO, PLUG_BEAMER, PLUG_MM, VU, Devices


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    yield


@pytest.fixture
async def devices(hass: HomeAssistant) -> Devices:
    """Fake devices, all powered off but present."""
    for entity_id in (ONKYO, BEAMER, VU, PLUG_BEAMER, PLUG_MM):
        hass.states.async_set(entity_id, "off")
    return Devices(hass)
