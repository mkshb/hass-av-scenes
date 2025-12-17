"""Simplified config flow for debugging."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AVScenesConfigFlowSimple(config_entries.ConfigFlow, domain=DOMAIN):
    """Simplified config flow for debugging."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        _LOGGER.info("DEBUG: Config flow user step called")
        
        if user_input is not None:
            _LOGGER.info("DEBUG: Creating entry")
            return self.async_create_entry(
                title="AV Scenes",
                data={"rooms": {}},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AVScenesOptionsFlowSimple:
        """Get the options flow for this handler."""
        _LOGGER.info("DEBUG: Creating options flow")
        return AVScenesOptionsFlowSimple(config_entry)


class AVScenesOptionsFlowSimple(config_entries.OptionsFlow):
    """Simplified options flow for debugging."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        _LOGGER.info("DEBUG: Options flow __init__ called")
        self.test_data = "initialized"

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options - simplified version."""
        _LOGGER.info("DEBUG: Options flow init step called")
        
        if user_input is not None:
            _LOGGER.info("DEBUG: User submitted: %s", user_input)
            test_value = user_input.get("test_input", "")
            
            # Update config entry
            _LOGGER.info("DEBUG: Updating config entry")
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={"rooms": {}, "test": test_value}
            )
            
            return self.async_create_entry(title="", data={})
        
        _LOGGER.info("DEBUG: Showing form")
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional("test_input", default=""): str,
            }),
        )
