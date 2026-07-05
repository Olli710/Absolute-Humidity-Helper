"""Absolute Humidity Sensor for Home Assistant."""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
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
    ICON_ABSOLUTE_HUMIDITY,
    ATTR_DEW_POINT,
    ATTR_TEMPERATURE,
    ATTR_RELATIVE_HUMIDITY,
    ATTR_ABSOLUTE_HUMIDITY,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Calculation helpers (unverändert)
# ---------------------------------------------------------------------------


def _saturation_vapor_pressure(temperature_c: float) -> float:
    """Calculate saturation vapor pressure (kPa) using Magnus formula."""
    return 0.61094 * math.exp((MAGNUS_A * temperature_c) / (temperature_c + MAGNUS_B))


def calculate_absolute_humidity(
    temperature: float,
    humidity: float,
    temp_unit: str = UnitOfTemperature.CELSIUS,
) -> Optional[float]:
    """Calculate absolute humidity in g/m³ from temperature and relative humidity."""
    try:
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
        absolute_humidity = (e * 1000.0) / (461.5 * T_kelvin) * 1000.0
        return absolute_humidity

    except (ValueError, TypeError, ZeroDivisionError) as err:
        _LOGGER.error("Error calculating absolute humidity: %s", err)
        return None


def calculate_dew_point(temperature_c: float, humidity: float) -> Optional[float]:
    """Calculate dew point in °C using the Magnus formula."""
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
    _attr_should_poll = False  # Wir aktualisieren über State-Change-Events

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
        self._device_id: str | None = None  # Wird in async_added_to_hass ermittelt

        self._attr_unique_id = config_entry.unique_id or DOMAIN
        self._attr_name = config_entry.title
        self._attr_icon = ICON_ABSOLUTE_HUMIDITY
        self._attr_suggested_display_precision = self._round_digits

    # ------------------------------------------------------------------
    # Device info & registry
    # ------------------------------------------------------------------
    @property
    def device_info(self) -> DeviceInfo | None:
        """
        Tie this sensor to the device of the temperature sensor,
        falls dieser einem Gerät zugeordnet ist.
        """
        if self._device_id:
            return DeviceInfo(identifiers={(DOMAIN, self._device_id)})

        # Fallback: eigenes virtuelles Gerät, falls keine Zuordnung möglich ist
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._attr_name,
            manufacturer="Home Assistant Community",
            model="Absolute Humidity Helper",
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Versuche, das Gerät des Temperatursensors zu ermitteln
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)

        temp_entry = ent_reg.async_get(self._temperature_sensor)
        if temp_entry and temp_entry.device_id:
            device = dev_reg.async_get(temp_entry.device_id)
            if device:
                # Wir "hängen" uns an dasselbe Device an, indem wir
                # dessen erste Identifier übernehmen.
                self._device_id = next(iter(device.identifiers))[1]
                _LOGGER.debug(
                    "Linking %s to existing device %s",
                    self.entity_id,
                    device.name,
                )

        # State-Change-Listener registrieren, damit sich der Sensor
        # sofort aktualisiert, wenn Quellsensoren sich ändern.
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._temperature_sensor, self._humidity_sensor],
                self._async_source_state_changed,
            )
        )

        # Initiale Berechnung
        self._recalculate()

    @callback
    def _async_source_state_changed(self, event) -> None:
        """Handle state changes of source sensors."""
        self._recalculate()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extended state attributes."""
        temp_state = self.hass.states.get(self._temperature_sensor)
        hum_state = self.hass.states.get(self._humidity_sensor)

        attrs: dict[str, Any] = {
            ATTR_TEMPERATURE: (
                temp_state.state
                if temp_state
                and temp_state.state
                not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "unavailable", "unknown")
                else STATE_UNKNOWN
            ),
            ATTR_RELATIVE_HUMIDITY: (
                hum_state.state
                if hum_state
                and hum_state.state
                not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "unavailable", "unknown")
                else STATE_UNKNOWN
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
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
            "unavailable",
            "unknown",
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
            return state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature.CELSIUS
            )
        return UnitOfTemperature.CELSIUS

    @property
    def available(self) -> bool:
        """Return True only when both source entities are available."""
        temp = self.hass.states.get(self._temperature_sensor)
        hum = self.hass.states.get(self._humidity_sensor)
        return bool(
            temp
            and hum
            and temp.state
            not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "unavailable", "unknown")
            and hum.state
            not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "unavailable", "unknown")
        )

    @property
    def native_value(self) -> Optional[float]:
        """Return the calculated absolute humidity value."""
        return self._state

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def _recalculate(self) -> None:
        """Recalculate absolute humidity and dew point (synchron, kein I/O)."""
        temperature = self._get_numeric_value(self._temperature_sensor)
        humidity = self._get_numeric_value(self._humidity_sensor)

        if temperature is None or humidity is None:
            self._state = None
            self._dew_point_state = None
            return

        temp_unit = self._get_temp_unit()
        abs_hum = calculate_absolute_humidity(temperature, humidity, temp_unit)
        self._state = (
            round(abs_hum, self._round_digits) if abs_hum is not None else None
        )

        if self._create_dew_point:
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

    async def async_update(self) -> None:
        """
        Wird nur noch als Fallback genutzt (should_poll=False),
        z.B. beim initialen update_before_add.
        """
        self._recalculate()


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

    async_add_entities(
        [
            AbsoluteHumiditySensor(
                config_entry=config_entry,
                temperature_sensor=temperature_sensor,
                humidity_sensor=humidity_sensor,
            )
        ],
        update_before_add=True,
    )


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
    name = config.get(CONF_NAME, DEFAULT_NAME)
    temperature_sensor = config.get(CONF_TEMPERATURE_SENSOR, "")
    humidity_sensor = config.get(CONF_HUMIDITY_SENSOR, "")
    create_dew_point = config.get(CONF_CREATE_DEW_POINT, True)
    round_digits = config.get(CONF_ROUND_DIGITS, DEFAULT_ROUND_DIGITS)

    if not temperature_sensor or not humidity_sensor:
        _LOGGER.error("Missing temperature_sensor or humidity_sensor in YAML config")
        return

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

    async_add_entities(
        [
            AbsoluteHumiditySensor(
                config_entry=_MockConfigEntry(),  # type: ignore[arg-type]
                temperature_sensor=temperature_sensor,
                humidity_sensor=humidity_sensor,
            )
        ],
        update_before_add=True,
    )
