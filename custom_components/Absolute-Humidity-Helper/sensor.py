"""Sensor platform for Absolute Humidity."""
from __future__ import annotations
from homeassistant.util.unit_conversion import TemperatureConverter


from homeassistant.components.sensor import (
    SensorDeviceClass,  # Hinzugefügt für die offizielle ABSOLUTE_HUMIDITY Klasse
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfDensity,      # Moderner Standard für g/m³ (ersetzt CONCENTRATION_GRAMS_PER_CUBIC_METER)
    UnitOfTemperature,  # Ersetzt das alte TEMPERATURE_CELSIUS
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities([AbsoluteHumiditySensor(entry)])

class AbsoluteHumiditySensor(SensorEntity):
    """Representation of an Absolute Humidity Sensor."""

    _attr_has_entity_name = True
    _attr_name = "Absolute Humidity"
    
    # Durch die korrekte Device Class weiß HA exakt, wie der Sensor zu behandeln ist
    _attr_device_class = SensorDeviceClass.ABSOLUTE_HUMIDITY
    _attr_native_unit_of_measurement = UnitOfDensity.GRAMS_PER_CUBIC_METER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, config_entry: ConfigEntry):
        """Initialize the sensor."""
        self._attr_unique_id = f"{config_entry.entry_id}-absolute_humidity"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": "Absolute Humidity Sensor",
            "manufacturer": "Custom",
        }
        self._config_entry = config_entry

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        from homeassistant.helpers.event import async_track_state_change_event

        async def _async_state_changed_listener(event) -> None:
            """Handle state changes of parent sensors."""
            self.async_write_ha_state()

        # Tracke Änderungen am Temperatursensor
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, 
                [self._config_entry.data["temperature_sensor"]], 
                _async_state_changed_listener
            )
        )
        # Tracke Änderungen am Luftfeuchtigkeitssensor
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, 
                [self._config_entry.data["humidity_sensor"]], 
                _async_state_changed_listener
            )
        )

    @property
    def available(self) -> bool:
        """Return True if both source sensors are online and have valid states."""
        temp_state = self.hass.states.get(self._config_entry.data["temperature_sensor"])
        rh_state = self.hass.states.get(self._config_entry.data["humidity_sensor"])
        
        return (
            temp_state is not None 
            and rh_state is not None 
            and temp_state.state not in (None, "unavailable", "unknown")
            and rh_state.state not in (None, "unavailable", "unknown")
        )

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

            # Einheit des Temperatursensors auslesen (Standard: Celsius)
            temp_unit = temp_sensor.attributes.get("unit_of_measurement", UnitOfTemperature.CELSIUS)
            
            # Falls nötig, automatisch in Celsius konvertieren
            temp_c = TemperatureConverter.convert(temp, temp_unit, UnitOfTemperature.CELSIUS)

            # Berechnung jetzt immer basierend auf temp_c (Celsius)
            ah = (6.112 * 2.537 * (10 ** ((7.5 * temp_c) / (237.7 + temp_c))) * rh * 2.1674) / (273.15 + temp_c)
            return round(ah, 2)
        except (ValueError, TypeError):
            return None