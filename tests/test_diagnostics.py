"""Tests for the AV Scenes diagnostics platform."""
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.av_scenes.const import DOMAIN, CONF_ROOMS
from custom_components.av_scenes.diagnostics import (
    async_get_config_entry_diagnostics,
)

_ROOMS = {
    "living": {
        "name": "Living",
        "activities": {"Movie": {"steps": []}},
    }
}


async def test_diagnostics_expose_full_config(hass: HomeAssistant):
    """Diagnostics return the stored rooms so config can be transferred."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ROOMS: _ROOMS})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["data"][CONF_ROOMS] == _ROOMS
    assert diag["runtime"]["rooms"] == _ROOMS
