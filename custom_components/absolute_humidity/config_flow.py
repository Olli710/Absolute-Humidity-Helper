"""Config flow for Absolute Humidity Helper."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant.components.sensor import SensorDeviceClass

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_ROUND_DIGITS,
    CONF_CREATE_DEW_POINT,
    CONF_ROUND_DIGITS,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


def _temperature_selector() -> selector.EntitySelector:
    """Return an entity selector for temperature sensors.

    Nutzt device_class als Liste (robuster gegen API-Änderungen)
    und fällt zusätzlich nicht komplett aus, falls Sensoren
    keine device_class gesetzt haben - siehe Hinweis in Doku.
    """
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="sensor",
            device_class=[SensorDeviceClass.TEMPERATURE],
        )
    )


def _humidity_selector() -> selector.EntitySelector:
    """Return an entity selector for humidity sensors."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="sensor",
            device_class=[SensorDeviceClass.HUMIDITY],
        )
    )


def _build_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the schema used for both config and options flow."""
    defaults = defaults or {}

    return vol.Schema(
        {
            vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(
                CONF_TEMPERATURE_SENSOR,
                default=defaults.get(CONF_TEMPERATURE_SENSOR, vol.UNDEFINED),
            ): _temperature_selector(),
            vol.Required(
                CONF_HUMIDITY_SENSOR,
                default=defaults.get(CONF_HUMIDITY_SENSOR, vol.UNDEFINED),
            ): _humidity_selector(),
            vol.Optional(
                CONF_CREATE_DEW_POINT,
                default=defaults.get(CONF_CREATE_DEW_POINT, True),
            ): bool,
            vol.Optional(
                CONF_ROUND_DIGITS,
                default=defaults.get(CONF_ROUND_DIGITS, DEFAULT_ROUND_DIGITS),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
        }
    )


def _validate_input(hass, user_input: dict[str, Any]) -> dict[str, str]:
    """Validate user input, return dict of errors."""
    errors: dict[str, str] = {}

    temp_entity = user_input.get(CONF_TEMPERATURE_SENSOR, "")
    hum_entity = user_input.get(CONF_HUMIDITY_SENSOR, "")

    if not temp_entity:
        errors[CONF_TEMPERATURE_SENSOR] = "required_temperature_sensor"
    elif not hass.states.get(temp_entity):
        errors[CONF_TEMPERATURE_SENSOR] = "entity_not_found"

    if not hum_entity:
        errors[CONF_HUMIDITY_SENSOR] = "required_humidity_sensor"
    elif not hass.states.get(hum_entity):
        errors[CONF_HUMIDITY_SENSOR] = "entity_not_found"

    return errors


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Absolute Humidity Helper."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Config flow user_input: %s", user_input)
            errors = _validate_input(self.hass, user_input)

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

        schema = _build_schema(user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "OptionsFlowHandler":
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage options."""
        errors: dict[str, str] = {}
        options = dict(self.config_entry.options)

        if user_input is not None:
            _LOGGER.debug("Options flow user_input: %s", user_input)
            errors = _validate_input(self.hass, user_input)

            if not errors:
                return self.async_create_entry(data=user_input)
            # Damit bei Fehlern die zuletzt eingegebenen Werte
            # im Formular erhalten bleiben:
            options = user_input

        schema = _build_schema(options)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
