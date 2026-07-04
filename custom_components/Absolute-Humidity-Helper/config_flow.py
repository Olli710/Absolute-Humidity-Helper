"""Config flow for Absolute Humidity integration."""
from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN


class AbsoluteHumidityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Absolute Humidity."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Hier könnte noch eine zusätzliche Validierung stattfinden falls nötig
            return self.async_create_entry(
                title="Absolute Humidity Sensor", data=user_input
            )

        # Definition des Schemas mit Filtern für die Geräteklassen
        data_schema = vol.Schema(
            {
                vol.Required("temperature_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class=SensorDeviceClass.TEMPERATURE,
                    )
                ),
                vol.Required("humidity_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class=SensorDeviceClass.HUMIDITY,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
