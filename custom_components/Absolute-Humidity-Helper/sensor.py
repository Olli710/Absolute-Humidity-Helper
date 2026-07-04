"""Sensor platform for Absolute Humidity."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    TEMPERATURE_CELSIUS,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities([AbsoluteHumiditySensor(entry)])

class AbsoluteHumiditySensor(SensorEntity):
    """Representation of an Absolute Humidity Sensor."""

    _attr_has_entity_name = True
    _attr_name = "Absolute Humidity"
    _attr_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, config_entry):
        """Initialize the sensor."""
        self._attr_unique_id = f"{config_entry.entry_id}-absolute_humidity"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": "Absolute Humidity Sensor",
            "manufacturer": "Custom",
        }
        self._config_entry = config_entry

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        temp_sensor = self.hass.states.get(self._config_entry.data["temperature_sensor"])
        rh_sensor = self.hass.states.get(self._config_entry.data["humidity_sensor"])

        if temp_sensor is None or rh_sensor is None:
            return None

        try:
            temp = float(temp_sensor.state)
            rh = float(rh_sensor.state)

            # Berechnung der absoluten Luftfeuchtigkeit in µg/m³
            # Formel: AH = (6.112 * 2.537 * 10^((7.5 * T)/(237.7 + T)) * RH * 2.1674) / (273.15 + T)
            ah = (6.112 * 2.537 * (10 ** ((7.5 * temp) / (237.7 + temp))) * rh * 2.1674) / (273.15 + temp)
            return round(ah, 2)
        except (ValueError, TypeError):
            return None
