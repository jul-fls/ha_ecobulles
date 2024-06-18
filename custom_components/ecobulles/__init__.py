"""The Ecobulles integration."""

from __future__ import annotations


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]
# PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Ecobulles from a config entry."""

    # Ensure DOMAIN key exists in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    eco_ref = entry.data.get("eco_ref")
    boitier_name = entry.data.get("name")
    num_serie = entry.data.get("num_serie")
    firmware_version = entry.data.get("firmware_version")

    # Create or get an instance of the device registry
    device_registry = dr.async_get(hass)

    # Create or update the device in the device registry
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, eco_ref)},  # Use eco_ref or another unique identifier
        name=boitier_name,
        manufacturer="Ecobulles",
        model="Ecobulles",
        sw_version=firmware_version,
        serial_number=num_serie,
    )

    # Store additional device-specific information in hass.data for internal use
    hass.data[DOMAIN][entry.entry_id] = {
        "eco_ref": eco_ref,
        "install_date": entry.data.get("install_date"),
        "last_date_receive": entry.data.get("last_date_receive"),
        "activated": entry.data.get("activated"),
        "locked": entry.data.get("locked"),
        "suspended": entry.data.get("suspended"),
        "suspended_time": entry.data.get("suspended_time"),
        "suspended_date": entry.data.get("suspended_date"),
        "last_alert": entry.data.get("last_alert"),
    }

    # Forward the entry setup to any platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # Safely remove the entry from hass.data
    if unload_ok:
        hass.data[DOMAIN].pop(
            entry.entry_id, None
        )  # Use pop with None as default to avoid KeyError

    return unload_ok
