"""Absolute Humidity Sensor for Home Assistant."""

from __future__ import annotations

import logging
import math

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_CREATE_DEW_POINT,
    CONF_HUMIDITY_SENSOR,
    CONF_ROUND_DIGITS,
    CONF_TEMPERATURE_SENSOR,
    DOMAIN,
    ICON_ABSOLUTE_HUMIDITY,
    ICON_DEW_POINT,
    MAGNUS_A,
    MAGNUS_B,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Absolute Humidity sensor from a config entry."""
    name = (
        config_entry.options.get(CONF_NAME)
        or config_entry.data.get(CONF_NAME)
        or "Absolute Humidity"
    )
    temp_sensor = config_entry.options.get(
        CONF_TEMPERATURE_SENSOR
    ) or config_entry.data.get(CONF_TEMPERATURE_SENSOR)
    hum_sensor = config_entry.options.get(
        CONF_HUMIDITY_SENSOR
    ) or config_entry.data.get(CONF_HUMIDITY_SENSOR)
    round_digits = config_entry.options.get(
        CONF_ROUND_DIGITS,
        config_entry.data.get(CONF_ROUND_DIGITS, 2),
    )
    create_dew_point = config_entry.options.get(
        CONF_CREATE_DEW_POINT,
        config_entry.data.get(CONF_CREATE_DEW_POINT, False),
    )

    entities = [
        AbsoluteHumiditySensor(
            config_entry=config_entry,
            name=name,
            temperature_sensor=str(temp_sensor),
            humidity_sensor=str(hum_sensor),
            round_digits=int(round_digits),
        ),
    ]

    if create_dew_point:
        entities.append(
            DewPointSensor(
                config_entry=config_entry,
                name=f"{name} Dew Point",
                temperature_sensor=str(temp_sensor),
                humidity_sensor=str(hum_sensor),
                round_digits=int(round_digits),
            ),
        )

    async_add_entities(entities)


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

    Formula: AH = 6.112 * exp((17.67 * T) / (T + 243.5)) * RH * 2.1674 / (273.15 + T)
    """
    saturation_vapor = 6.112 * math.exp(
        (17.67 * temperature_c) / (temperature_c + 243.5)
    )
    actual_vapor = saturation_vapor * (relative_humidity / 100.0)
    absolute_humidity = (actual_vapor * 2.1674) / (273.15 + temperature_c)
    return max(0.0, absolute_humidity)


def calculate_dew_point(temperature_c: float, relative_humidity: float) -> float:
    """Calculate dew point in °C using the Magnus formula."""
    if relative_humidity <= 0 or relative_humidity > 100:
        return float("nan")

    gamma = math.log(relative_humidity / 100.0) + (MAGNUS_A * temperature_c) / (
        MAGNUS_B + temperature_c
    )
    dew_point = (MAGNUS_B * gamma) / (MAGNUS_A - gamma)
    return dew_point


class _BaseHumiditySensor(SensorEntity):
    """Base class for absolute humidity and dew point sensors."""

    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        config_entry: ConfigEntry | None,
        name: str,
        temperature_sensor: str,
        humidity_sensor: str,
        round_digits: int,
    ) -> None:
        self._config_entry = config_entry
        self._name = name
        self._temperature_sensor = temperature_sensor
        self._humidity_sensor = humidity_sensor
        self._round_digits = round_digits
        self._source_device_id: str | None = None
        self._attr_unique_id: str | None = (
            config_entry.entry_id if config_entry else None
        )
        self._attr_name = name

    def _resolve_source_device_id(self) -> str | None:
        """Resolve the source device ID from the temperature sensor's entity registry entry.

        Looks up the entity registry entry for the temperature sensor, then resolves
        its device_id to a device in the device registry. Returns the first identifier
        value of that device (or the device_id itself as fallback).
        """
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)

        temp_entry = entity_registry.async_get(self._temperature_sensor)
        if temp_entry is None or not temp_entry.device_id:
            return None

        device = device_registry.async_get(temp_entry.device_id)
        if device is None:
            return None

        # Prefer the first identifier tuple's value as the stable device reference
        if device.identifiers:
            first_ident = next(iter(device.identifiers), None)
            if first_ident is not None:
                return first_ident[1] if len(first_ident) > 1 else first_ident[0]

        # Fallback: use the device_id string directly
        return str(temp_entry.device_id)

    async def async_added_to_hass(self) -> None:
        """Subscribe to source entity state changes and compute initial state."""
        self._source_device_id = self._resolve_source_device_id()

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
        """Recalculate from current source states."""
        temp_state = self.hass.states.get(self._temperature_sensor)
        hum_state = self.hass.states.get(self._humidity_sensor)

        temperature = _parse_state(temp_state)
        humidity = _parse_state(hum_state)

        if temperature is None or humidity is None:
            self._attr_native_value = None
            return

        try:
            value = self._compute_value(temperature, humidity)
            if value is not None and not math.isnan(value):
                self._attr_native_value = round(value, self._round_digits)
            else:
                self._attr_native_value = None
        except Exception:  # noqa: BLE001
            self._attr_native_value = None

        self.async_write_ha_state()

    def _compute_value(self, temperature: float, humidity: float) -> float | None:
        """Override in subclass to compute the sensor value."""
        raise NotImplementedError


class AbsoluteHumiditySensor(_BaseHumiditySensor):
    """Representation of an Absolute Humidity sensor."""

    _attr_native_unit_of_measurement = "g/m³"
    _attr_icon = ICON_ABSOLUTE_HUMIDITY

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class."""
        return SensorDeviceClass.ABSOLUTE_HUMIDITY

    def _compute_value(self, temperature: float, humidity: float) -> float | None:
        """Compute absolute humidity in g/m³."""
        return calculate_absolute_humidity(temperature, humidity)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information, linked to the source temperature sensor's device."""
        if self._source_device_id:
            # Register as part of the source device (not a separate "via" device)
            return DeviceInfo(
                identifiers={(DOMAIN, self._source_device_id)},
                name=self._name,
                manufacturer="Absolute Humidity Helper",
                model="Virtual Sensor",
            )
        # Fallback: standalone device when no source device found
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id or str(id(self)))},
            name=self._name,
            manufacturer="Absolute Humidity Helper",
            model="Virtual Sensor",
        )


class DewPointSensor(_BaseHumiditySensor):
    """Representation of a Dew Point sensor (linked to the Absolute Humidity sensor)."""

    _attr_native_unit_of_measurement = "°C"
    _attr_icon = ICON_DEW_POINT

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class."""
        return SensorDeviceClass.TEMPERATURE

    def _compute_value(self, temperature: float, humidity: float) -> float | None:
        """Compute dew point in °C."""
        return calculate_dew_point(temperature, humidity)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information, linked via via_device to the Absolute Humidity sensor's device."""
        if self._source_device_id:
            # Dew Point is a sub-device via the Absolute Humidity sensor device
            return DeviceInfo(
                identifiers={(DOMAIN, f"{self._source_device_id}_dew_point")},
                via_device=(DOMAIN, self._source_device_id),
                name=self._name,
                manufacturer="Absolute Humidity Helper",
                model="Virtual Sensor",
            )
        # Fallback: standalone device when no source device found
        return DeviceInfo(
            identifiers={(DOMAIN, f"dew_point_{self.unique_id or id(self)}")},
            name=self._name,
            manufacturer="Absolute Humidity Helper",
            model="Virtual Sensor",
        )
