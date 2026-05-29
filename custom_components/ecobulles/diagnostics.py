"""Diagnostics support for Ecobulles."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    "active_alerts",
    "eco_ref",
    "num_serie",
    "serial_number",
    "user_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator_data: dict[str, Any] = {}
    if hasattr(entry, "runtime_data"):
        coordinator_data = getattr(entry.runtime_data.coordinator, "data", {}) or {}

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": async_redact_data(dict(coordinator_data), TO_REDACT),
    }
