"""Config flow for Absolute Humidity integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN

class AbsoluteHumidityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Absolute Humidity."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: dict[str, any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("temperature_sensor"): selector.EntitySelector(
                            selector.EntitySelectorConfig(domain="sensor")
                        ),
                        vol.Required("humidity_sensor"): selector.EntitySelector(
                            selector.EntitySelectorConfig(domain="sensor")
                        ),
                    }
                ),
            )

        # Hier könntest du die Eingaben validieren
        return self.async_create_entry(
            title="Absolute Humidity Sensor",
            data=user_input,
        )