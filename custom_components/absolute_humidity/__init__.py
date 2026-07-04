"""Absolute Humidity Helper for Home Assistant."""
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN as DOMAIN

async def async_setup_entry(hass, entry: ConfigEntry):
    """Set up Absolute Humidity Helper from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass, entry: ConfigEntry):
    """Unload the config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
