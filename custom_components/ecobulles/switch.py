"""Switch platform for Ecobulles."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ENABLE_RAW_CO2_SENSOR, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ecobulles switches."""
    async_add_entities([RawCO2DebugSwitch(hass, entry)])


class RawCO2DebugSwitch(SwitchEntity):
    """Enable or disable the raw CO2 diagnostic sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "raw_co2_debug"
    _attr_icon = "mdi:bug-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.data['eco_ref']}_raw_co2_debug"

    @property
    def is_on(self) -> bool:
        """Return whether raw CO2 diagnostics are enabled."""
        return bool(self.entry.options.get(CONF_ENABLE_RAW_CO2_SENSOR, False))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable raw CO2 diagnostics."""
        await self._update_option(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable raw CO2 diagnostics."""
        await self._update_option(False)

    async def _update_option(self, enabled: bool) -> None:
        """Persist the debug option and refresh the switch."""
        options = {**self.entry.options, CONF_ENABLE_RAW_CO2_SENSOR: enabled}
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self.async_write_ha_state()
        await self.hass.config_entries.async_reload(self.entry.entry_id)

    @property
    def device_info(self):
        """Return device registry metadata."""
        return {"identifiers": {(DOMAIN, self.entry.data["eco_ref"])}}
