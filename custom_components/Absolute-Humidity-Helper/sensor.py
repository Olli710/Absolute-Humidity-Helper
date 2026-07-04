"""Sensor platform for Absolute Humidity."""
from __future__ import annotations

import logging
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfDensity,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Absolute Humidity sensor entry."""
    temp_sensor_id = entry.data["temperature_sensor"]
    humidity_sensor_id = entry.data["humidity_sensor"]

    async_add_entities(
        [
            AbsoluteHumiditySensor(
                entry,
                temp_sensor_id,
                humidity_sensor_id,
            )
        ]
    )


class AbsoluteHumiditySensor(SensorEntity):
    """Representation of an Absolute Humidity Sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ABSOLUTE_HUMIDITY
    _attr_native_unit_of_measurement = UnitOfDensity.GRAMS_PER_CUBIC_METER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        config_entry: ConfigEntry,
        temp_sensor_id: str,
        humidity_sensor_id: str,
    ) -> None:
        """Initialize the sensor."""
        self._config_entry = config_entry
        self._temp_sensor_id = temp_sensor_id
        self._humidity_sensor_id = humidity_sensor_id
        
        # Einzigartige ID für diesen Sensor generieren
        self._attr_unique_id = f"{config_entry.entry_id}_absolute_humidity"
        
        # Standardname, falls keine Gerätezuordnung gefunden wird
        self._attr_name = "Absolute Luftfeuchtigkeit"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Link this sensor to the device of the source humidity sensor."""
        # Wir holen uns das Entity Registry, um nachzusehen, zu welchem Gerät 
        # der Quell-Feuchtigkeitssensor gehört.
        ent_reg = er.async_get(self.hass)
        source_entity = ent_reg.async_get(self._humidity_sensor_id)
        
        if source_entity and source_entity.device_id:
            # Wenn ein Gerät gefunden wurde, holen wir uns dessen Infos aus der Device Registry
            dev_reg = dr.async_get(self.hass)
            device = dev_reg.async_get(source_entity.device_id)
            
            if device:
                # Wir geben die Identifikatoren des Quellgeräts zurück.
                # Home Assistant merkt dadurch: "Ah, dieser neue Sensor gehört zu diesem Gerät!"
                return DeviceInfo(
                    identifiers=device.identifiers,
                    connections=device.connections,
                )
        return None

    @property
    def native_value(self) -> float | None:
        """Calculate the absolute humidity state."""
        temp_sensor = self.hass.states.get(self._temp_sensor_id)
        rh_sensor = self.hass.states.get(self._humidity_sensor_id)

        if temp_sensor is None or rh_sensor is None:
            return None

        try:
            temp = float(temp_sensor.state)
            rh = float(rh_sensor.state)

            # Einheit des Quell-Sensors bestimmen (Fallback auf Celsius)
            temp_unit = temp_sensor.attributes.get(
                "unit_of_measurement", UnitOfTemperature.CELSIUS
            )
            
            # Automatisch zu Celsius konvertieren, falls der Sensor Fahrenheit liefert
            temp_c = TemperatureConverter.convert(
                temp, temp_unit, UnitOfTemperature.CELSIUS
            )

            # Formel für absolute Feuchtigkeit in g/m³
            ah = (
                6.112
                * 2.537
                * (10 ** ((7.5 * temp_c) / (237.7 + temp_c)))
                * rh
                * 2.1674
            ) / (273.15 + temp_c)
            
            return round(ah, 2)
        except (ValueError, TypeError):
            return None
