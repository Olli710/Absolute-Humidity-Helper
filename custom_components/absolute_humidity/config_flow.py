"""Config flow for Absolute Humidity Helper."""
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_ROUND_DIGITS,
    CONF_CREATE_DEW_POINT,
    CONF_ROUND_DIGITS,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Absolute Humidity Helper."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            temp_entity = user_input.get(CONF_TEMPERATURE_SENSOR, "")
            hum_entity = user_input.get(CONF_HUMIDITY_SENSOR, "")

            if not temp_entity:
                errors[CONF_TEMPERATURE_SENSOR] = "required_temperature_sensor"
            if not hum_entity:
                errors[CONF_HUMIDITY_SENSOR] = "required_humidity_sensor"

            if temp_entity and not self.hass.states.get(temp_entity):
                errors[CONF_TEMPERATURE_SENSOR] = "entity_not_found"
            if hum_entity and not self.hass.states.get(hum_entity):
                errors[CONF_HUMIDITY_SENSOR] = "entity_not_found"

            if not errors:
                name = user_input.get(CONF_NAME, DEFAULT_NAME)
                unique_id = f"absolute_humidity_{name.lower().replace(' ', '_')}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={},
                    options=user_input,
                )

        schema = {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Required(CONF_TEMPERATURE_SENSOR): str,
            vol.Required(CONF_HUMIDITY_SENSOR): str,
            vol.Optional(CONF_CREATE_DEW_POINT, default=True): bool,
            vol.Optional(CONF_ROUND_DIGITS, default=DEFAULT_ROUND_DIGITS): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=6)
            ),
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        """Manage options."""
        errors: dict[str, str] = {}
        options = self.config_entry.options

        if user_input is not None:
            temp_entity = user_input.get(CONF_TEMPERATURE_SENSOR, "")
            hum_entity = user_input.get(CONF_HUMIDITY_SENSOR, "")

            if not temp_entity:
                errors[CONF_TEMPERATURE_SENSOR] = "required_temperature_sensor"
            if not hum_entity:
                errors[CONF_HUMIDITY_SENSOR] = "required_humidity_sensor"

            if temp_entity and not self.hass.states.get(temp_entity):
                errors[CONF_TEMPERATURE_SENSOR] = "entity_not_found"
            if hum_entity and not self.hass.states.get(hum_entity):
                errors[CONF_HUMIDITY_SENSOR] = "entity_not_found"

            if not errors:
                return self.async_create_entry(data=user_input)

        schema = {
            vol.Optional(
                CONF_NAME,
                default=options.get(CONF_NAME, DEFAULT_NAME),
            ): str,
            vol.Optional(
                CONF_TEMPERATURE_SENSOR,
                default=options.get(CONF_TEMPERATURE_SENSOR, ""),
            ): str,
            vol.Optional(
                CONF_HUMIDITY_SENSOR,
                default=options.get(CONF_HUMIDITY_SENSOR, ""),
            ): str,
            vol.Optional(
                CONF_CREATE_DEW_POINT,
                default=options.get(CONF_CREATE_DEW_POINT, True),
            ): bool,
            vol.Optional(
                CONF_ROUND_DIGITS,
                default=options.get(CONF_ROUND_DIGITS, DEFAULT_ROUND_DIGITS),
            ): vol.All(int, vol.Range(min=0, max=6)),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
        )
