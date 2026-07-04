"""Constants for Absolute Humidity Helper."""

from homeassistant.const import (
    UnitOfTemperature,
)

DOMAIN = "absolute_humidity"
DEFAULT_NAME = "Absolute Humidity"
DEFAULT_ROUND_DIGITS = 1

CONF_CREATE_DEW_POINT = "create_dew_point"
CONF_ROUND_DIGITS = "round_digits"
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"

# Constants for Magnus formula (dew point)
MAGNUS_A = 17.67
MAGNUS_B = 243.5
EPSILON = 0.000001  # Avoid division by zero

# Icons
ICON_ABSOLUTE_HUMIDITY = "mdi:water-percent"
ICON_DEW_POINT = "mdi:thermometer-water"

ATTR_DEW_POINT = "dew_point"
ATTR_TEMPERATURE = "temperature"
ATTR_RELATIVE_HUMIDITY = "relative_humidity"
ATTR_ABSOLUTE_HUMIDITY = "absolute_humidity"

SUPPORTED_UNIT_TEMP = {
    UnitOfTemperature.CELSIUS: UnitOfTemperature.CELSIUS,
    UnitOfTemperature.FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
}
