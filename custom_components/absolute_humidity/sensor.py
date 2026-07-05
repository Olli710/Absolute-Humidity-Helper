"""Absolute Humidity Sensor for Home Assistant."""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry as dr, entity_registry as er

try:
    from homeassistant.components.sensor import SensorDeviceClass
except ImportError:
    SensorDeviceClass = None  # type: ignore[assignment, misc]

try:
    from homeassistant.helpers.entity import DeviceInfo
except ImportError:
    from homeassistant.helpers.device_registry import DeviceInfo as DeviceInfo

from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_CREATE_DEW_POINT,
    CONF_HUMIDITY_SENSOR,
    CONF_NAME,
    CONF_ROUND_DIGITS,
    CONF_TEMPERATURE_SENSOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Absolute Humidity sensor from a config entry."""
    name = config_entry.data.get(CONF_NAME) or "Absolute Humidity"
    temp_sensor = config_entry.data[CONF_TEMPERATURE_SENSOR]
    hum_sensor = config_entry.data[CONF_HUMIDITY_SENSOR]
    round_digits = config_entry.data.get(CONF_ROUND_DIGITS, 2)
    create_dew_point = config_entry.options.get(
        CONF_CREATE_DEW_POINT,
        config_entry.data.get(CONF_CREATE_DEW_POINT, False),
    )

    async_add_entities(
        [
            AbsoluteHumiditySensor(
                config_entry=config_entry,
                name=name,
                temperature_sensor=temp_sensor,
                humidity_sensor=hum_sensor,
                round_digits=round_digits,
                create_dew_point=create_dew_point,
            ),
        ],
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Absolute Humidity sensor via YAML (deprecated)."""
    _LOGGER.warning(
        "YAML configuration of absolute_humidity is deprecated. "
        "Please use the UI to configure the sensor.",
    )

    temp_sensor = config.get(CONF_TEMPERATURE_SENSOR)
    hum_sensor = config.get(CONF_HUMIDITY_SENSOR)

    if not temp_sensor or not hum_sensor:
        _LOGGER.error(
            "YAML config requires %s and %s",
            CONF_TEMPERATURE_SENSOR,
            CONF_HUMIDITY_SENSOR,
        )
        return

    async_add_entities(
        [
            AbsoluteHumiditySensor(
                config_entry=None,
                name=config.get(CONF_NAME, "Absolute Humidity"),
                temperature_sensor=temp_sensor,
                humidity_sensor=hum_sensor,
                round_digits=config.get(CONF_ROUND_DIGITS, 2),
                create_dew_point=config.get(CONF_CREATE_DEW_POINT, False),
            ),
        ],
    )


def _parse_state(state: State | None) -> float | None:
    """Return float value from a State, or None if unavailable."""
    if state is None:
        return None
    if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return None


def calculate_absolute_humidity(
    temperature_c: float, relative_humidity: float
) -> float:
    """Calculate absolute humidity in g/m³ from temperature (°C) and relative humidity (%).

    Formula: AH = 6.112 * exp((17.67 * T)/(T+243.5)) * RH * 2.1674 / (273.15 + T)
    """
    saturation_vapor = 6.112 * math.exp(
        (17.67 * temperature_c) / (temperature_c + 243.5)
    )
    actual_vapor = saturation_vapor * (relative_humidity / 100.0)
    absolute_humidity = (actual_vapor * 2.1674) / (273.15 + temperature_c)
    return max(0.0, absolute_humidity)


class AbsoluteHumiditySensor(SensorEntity):
    """Representation of an Absolute Humidity sensor."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = "g/m³"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        config_entry: ConfigEntry | None,
        name: str,
        temperature_sensor: str,
        humidity_sensor: str,
        round_digits: int,
        create_dew_point: bool,
    ) -> None:
        self._config_entry = config_entry
        self._name = name
        self._temperature_sensor = temperature_sensor
        self._humidity_sensor = humidity_sensor
        self._round_digits = round_digits
        self._device_id: str | None = None
        self._attr_unique_id: str | None = (
            config_entry.entry_id if config_entry else None
        )
        self._attr_name = name

    async def async_added_to_hass(self) -> None:
        """Set up the sensor: resolve device ID, subscribe to state changes, compute initial state."""
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)

        temp_entry = entity_registry.async_get(self._temperature_sensor)
        if temp_entry and temp_entry.device_id:
            device = device_registry.async_get(temp_entry.device_id)
            if device and device.identifiers:
                first_id_tuple = next(iter(device.identifiers), None)
                if first_id_tuple is not None:
                    self._device_id = first_id_tuple[1]

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._temperature_sensor, self._humidity_sensor],
                self._async_state_changed,
            ),
        )
        await self._update_state()

    @callback
    def _async_state_changed(
        self,
        changed_entity: str,
        old_state: State | None,
        new_state: State | None,
    ) -> None:
        """Handle state changes of either source entity."""
        self.hass.async_create_task(self._update_state())

    async def _update_state(self) -> None:
        """Recalculate absolute humidity from current source states."""
        temp_state = self.hass.states.get(self._temperature_sensor)
        hum_state = self.hass.states.get(self._humidity_sensor)

        temperature = _parse_state(temp_state)
        humidity = _parse_state(hum_state)

        if temperature is None or humidity is None:
            self._attr_native_value = None
        else:
            try:
                ah = calculate_absolute_humidity(temperature, humidity)
                self._attr_native_value = round(ah, self._round_digits)
            except Exception:  # noqa: BLE001
                self._attr_native_value = None

        self.async_write_ha_state()

    @property
    def device_class(self) -> Any:
        """Return the device class."""
        if SensorDeviceClass is None:
            return None
        try:
            return SensorDeviceClass.ABSOLUTE_HUMIDITY
        except AttributeError:
            return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information, linking to the temperature sensor's device if found."""
        if self._device_id:
            return {"identifiers": {(DOMAIN, self._device_id)}}
        return {
            "identifiers": {(DOMAIN, self.unique_id or str(id(self)))},
            "name": self._name,
            "manufacturer": "Absolute Humidity Helper",
            "model": "Virtual Sensor",
        }
