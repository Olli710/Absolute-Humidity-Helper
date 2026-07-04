"""Absolute Humidity Sensor for Home Assistant."""
from __future__ import annotations

import logging
import math
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_ROUND_DIGITS,
    CONF_CREATE_DEW_POINT,
    CONF_ROUND_DIGITS,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    MAGNUS_A,
    MAGNUS_B,
    EPSILON,
    ICON_ABSOLUTE_HUMIDITY,
    ICON_DEW_POINT,
    ATTR_DEW_POINT,
    ATTR_TEMPERATURE,
    ATTR_RELATIVE_HUMIDITY,
    ATTR_ABSOLUTE_HUMIDITY,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Calculation helpers
# ---------------------------------------------------------------------------

def _saturation_vapor_pressure(temperature_c: float) -> float:
    """Calculate saturation vapor pressure (kPa) using Magnus formula."""
    return 0.61094 * math.exp((MAGNUS_A * temperature_c) / (temperature_c + MAGNUS_B))


def calculate_absolute_humidity(
    temperature: float,
    humidity: float,
    temp_unit: str = UnitOfTemperature.CELSIUS,
) -> Optional[float]:
    """
    Calculate absolute humidity in g/m³ from temperature and relative humidity.

    Uses:  AH (g/m³) = (e × 1000) / (461.5 × T_K)
    where e = vapor pressure (kPa), T_K = temperature in Kelvin.
    """
    try:
        # Normalise temperature to Celsius
        temperature_c = (
            (temperature - 32) * 5.0 / 9.0
            if temp_unit == UnitOfTemperature.FAHRENHEIT
            else temperature
        )

        if not (-50 <= temperature_c <= 60):
            _LOGGER.warning(
                "Temperature %.1f °C outside valid range -50 … 60", temperature_c
            )
            return None
        if not (0 <= humidity <= 100):
            _LOGGER.warning("Humidity %.1f %% outside valid range 0 … 100", humidity)
            return None

        e = (humidity / 100.0) * _saturation_vapor_pressure(temperature_c)
        T_kelvin = temperature_c + 273.15
        # kPa → Pa (×1000), result g/m³
        absolute_humidity = (e * 1000.0) / (461.5 * T_kelvin) * 1000.0
        return absolute_humidity

    except (ValueError, TypeError, ZeroDivisionError) as err:
        _LOGGER.error("Error calculating absolute humidity: %s", err)
        return None


def calculate_dew_point(temperature_c: float, humidity: float) -> Optional[float]:
    """
    Calculate dew point in °C using the Magnus formula.

    Td = (B·γ) / (A − γ)
    γ = (A·T) / (B+T) + ln(RH/100)
    """
    try:
        if not (0 < humidity <= 100):
            return None
        gamma = (MAGNUS_A * temperature_c) / (MAGNUS_B + temperature_c) + math.log(
            humidity / 100.0
        )
        return (MAGNUS_B * gamma) / (MAGNUS_A - gamma)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


# ---------------------------------------------------------------------------
# Entity implementation
# ---------------------------------------------------------------------------

class AbsoluteHumiditySensor(SensorEntity):
    """Sensor that calculates absolute humidity from temperature & humidity."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "g/m³"

    def __init__(
        self,
        config_entry: ConfigEntry,
        temperature_sensor: str,
        humidity_sensor: str,
    ) -> None:
        """Initialise the sensor."""
        self._config = config_entry
        self._temperature_sensor = temperature_sensor
        self._humidity_sensor = humidity_sensor
        self._round_digits: int = config_entry.options.get(
            CONF_ROUND_DIGITS, DEFAULT_ROUND_DIGITS
        )
        self._create_dew_point: bool = config_entry.options.get(
            CONF_CREATE_DEW_POINT, True
        )
        self._state: Optional[float] = None
        self._dew_point_state: Optional[float] = None

        self._attr_unique_id = config_entry.unique_id or DOMAIN
        self._attr_name = config_entry.title
        self._attr_icon = ICON_ABSOLUTE_HUMIDITY
        self._attr_suggested_display_precision = self._round_digits

    # ------------------------------------------------------------------
    # Device info & registry
    # ------------------------------------------------------------------
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information to tie this sensor to source sensors."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._attr_name,
            manufacturer="Home Assistant Community",
            model="Absolute Humidity Helper",
            sw_version=self._config.version,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extended state attributes."""
        temp_state = self.hass.states.get(self._temperature_sensor)
        hum_state = self.hass.states.get(self._humidity_sensor)

        attrs: dict[str, Any] = {
            ATTR_TEMPERATURE: (
                temp_state.state if temp_state and temp_state.state not in (
                    STATE_UNAVAILABLE, STATE_UNKNOWN, "unavailable", "unknown"
                ) else STATE_UNKNOWN
            ),
            ATTR_RELATIVE_HUMIDITY: (
                hum_state.state if hum_state and hum_state.state not in (
                    STATE_UNAVAILABLE, STATE_UNKNOWN, "unavailable", "unknown"
                ) else STATE_UNKNOWN
            ),
        }
        if self._create_dew_point and self._dew_point_state is not None:
            attrs[ATTR_DEW_POINT] = round(self._dew_point_state, self._round_digits)
        attrs[ATTR_ABSOLUTE_HUMIDITY] = self._state
        return attrs

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def _get_numeric_value(self, entity_id: str) -> Optional[float]:
        """Extract a numeric value from an entity state."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (
            STATE_UNAVAILABLE, STATE_UNKNOWN, "unavailable", "unknown"
        ):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            _LOGGER.warning("Cannot convert state '%s' to float", state.state)
            return None

    def _get_temp_unit(self) -> str:
        """Read the temperature unit from the temperature sensor."""
        state = self.hass.states.get(self._temperature_sensor)
        if state and hasattr(state, "attributes"):
            return state.attributes.get(ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature.CELSIUS)
        return UnitOfTemperature.CELSIUS

    @property
    def available(self) -> bool:
        """Return True only when both source entities are available."""
        temp = self.hass.states.get(self._temperature_sensor)
        hum = self.hass.states.get(self._humidity_sensor)
        return bool(temp and hum and temp.state not in (
            STATE_UNAVAILABLE, STATE_UNKNOWN, "unavailable", "unknown"
        ) and hum.state not in (
            STATE_UNAVAILABLE, STATE_UNKNOWN, "unavailable", "unknown"
        ))

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    async def async_update(self) -> None:
        """Recalculate absolute humidity and dew point."""
        temperature = self._get_numeric_value(self._temperature_sensor)
        humidity = self._get_numeric_value(self._humidity_sensor)

        if temperature is None or humidity is None:
            self._state = None
            self._dew_point_state = None
            return

        temp_unit = self._get_temp_unit()
        abs_hum = calculate_absolute_humidity(temperature, humidity, temp_unit)
        self._state = round(abs_hum, self._round_digits) if abs_hum is not None else None

        if self._create_dew_point:
            # Dew-point formula works in Celsius
            temp_c = (
                TemperatureConverter.convert(
                    temperature, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
                )
                if temp_unit == UnitOfTemperature.FAHRENHEIT
                else temperature
            )
            dp = calculate_dew_point(temp_c, humidity)
            if dp is not None:
                self._dew_point_state = (
                    TemperatureConverter.convert(
                        dp, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
                    )
                    if temp_unit == UnitOfTemperature.FAHRENHEIT
                    else dp
                )
            else:
                self._dew_point_state = None
        else:
            self._dew_point_state = None


# ---------------------------------------------------------------------------
# Entry setup (UI / config flow)
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor via UI (Config Flow)."""
    temperature_sensor = config_entry.options.get(CONF_TEMPERATURE_SENSOR, "")
    humidity_sensor = config_entry.options.get(CONF_HUMIDITY_SENSOR, "")

    async_add_entities([
        AbsoluteHumiditySensor(
            config_entry=config_entry,
            temperature_sensor=temperature_sensor,
            humidity_sensor=humidity_sensor,
        )
    ], update_before_add=True)


# ---------------------------------------------------------------------------
# YAML platform setup (legacy)
# ---------------------------------------------------------------------------

async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the sensor via YAML configuration."""
    from .const import CONF_TEMPERATURE_SENSOR, CONF_HUMIDITY_SENSOR

    name = config.get(CONF_NAME, DEFAULT_NAME)
    temperature_sensor = config.get(CONF_TEMPERATURE_SENSOR, "")
    humidity_sensor = config.get(CONF_HUMIDITY_SENSOR, "")
    create_dew_point = config.get(CONF_CREATE_DEW_POINT, True)
    round_digits = config.get(CONF_ROUND_DIGITS, DEFAULT_ROUND_DIGITS)

    if not temperature_sensor or not humidity_sensor:
        _LOGGER.error("Missing temperature_sensor or humidity_sensor in YAML config")
        return

    # Create a minimal mock ConfigEntry for the entity constructor
    class _MockConfigEntry:
        unique_id = f"absolute_humidity_{name.lower().replace(' ', '_')}"
        title = name
        options = {
            CONF_CREATE_DEW_POINT: create_dew_point,
            CONF_ROUND_DIGITS: round_digits,
            CONF_TEMPERATURE_SENSOR: temperature_sensor,
            CONF_HUMIDITY_SENSOR: humidity_sensor,
        }
        version = "YAML"

    async_add_entities([
        AbsoluteHumiditySensor(
            config_entry=_MockConfigEntry(),  # type: ignore[arg-type]
            temperature_sensor=temperature_sensor,
            humidity_sensor=humidity_sensor,
        )
    ], update_before_add=True)
