"""Initialize the Absolute Humidity integration."""
import asyncio
import importlib

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Absolute Humidity from a config entry."""
    
    # ... (Dein bisheriger Setup-Code, falls vorhanden) ...

    # NEU: Plattformen im Hintergrund-Thread (Executor) vorab importieren,
    # um blockierende I/O-Zugriffe im Event-Loop unter Python 3.14+ zu verhindern.
    await asyncio.gather(*[
        hass.async_add_executor_job(
            importlib.import_module,
            f"custom_components.absolute_humidity.{platform}"
        )
        for platform in PLATFORMS
    ])

    # Dein bisheriger Aufruf (jetzt ohne Blocking-Fehler):
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
