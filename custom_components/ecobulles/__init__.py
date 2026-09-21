"""The Ecobulles integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .api import EcobullesClient
from .const import DOMAIN
from .device import model_from_serial_number
from .sensor import EcobullesCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]
_LOGGER = logging.getLogger(__name__)


@dataclass
class EcobullesRuntimeData:
    """Runtime data stored on the config entry."""

    coordinators: dict[str, EcobullesCoordinator]

    @property
    def coordinator(self) -> EcobullesCoordinator:
        """Keep compatibility with the original single-box runtime data."""
        return next(iter(self.coordinators.values()))


def _box_metadata(box: dict[str, Any]) -> dict[str, Any]:
    """Keep only the device metadata needed to create the HA device."""
    return {
        "eco_ref": str(box["eco_ref"]),
        "name": box.get("name"),
        "num_serie": box.get("num_serie"),
        "firmware_version": box.get("firm_ver") or box.get("firmware_version"),
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ecobulles from a config entry."""

    # Ensure DOMAIN key exists in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    client = EcobullesClient(
        hass,
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
    )
    saved_boxes = entry.data.get("devices") or [
        {
            "eco_ref": entry.data["eco_ref"],
            "name": entry.data.get("name"),
            "num_serie": entry.data.get("num_serie"),
            "firmware_version": entry.data.get("firmware_version"),
        }
    ]
    try:
        discovered = await client.list_devices()
    except (RuntimeError, TimeoutError):
        _LOGGER.warning("Cannot refresh Ecobulles account device list; using saved devices")
        discovered = []
    boxes = [_box_metadata(box) for box in discovered if box.get("eco_ref")]
    if not boxes:
        boxes = saved_boxes
    # Preserve original metadata if the listing omits a field used by the device registry.
    saved_by_ref = {box["eco_ref"]: box for box in saved_boxes}
    boxes = [
        {
            **saved_by_ref.get(box["eco_ref"], {}),
            **{key: value for key, value in box.items() if value is not None},
        }
        for box in boxes
    ]
    boxes.sort(key=lambda box: box["eco_ref"] != entry.data["eco_ref"])
    account_id = client.account_id or entry.data.get("user_id")
    account_name = client.account_name or entry.data.get("account_name")
    updated_data = {
        **entry.data,
        "devices": boxes,
        "user_id": account_id,
        "account_name": account_name,
    }
    account_key = f"account_{account_id}" if account_id else entry.unique_id
    old_name = entry.data.get("account_name") or entry.data.get("name")
    generated_titles = {
        "Ecobulles",
        f"Ecobulles : {old_name}",
        f"Ecobulles: {old_name}",
    }
    title = (
        f"Ecobulles: {account_name}"
        if account_name and entry.title in generated_titles
        else entry.title
    )
    if (
        updated_data != dict(entry.data)
        or account_key != entry.unique_id
        or title != entry.title
    ):
        hass.config_entries.async_update_entry(
            entry, data=updated_data, unique_id=account_key, title=title
        )

    device_registry = dr.async_get(hass)
    coordinators: dict[str, EcobullesCoordinator] = {}
    for box in boxes:
        eco_ref = box["eco_ref"]
        serial = box.get("num_serie")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, eco_ref)},
            name=box.get("name"),
            manufacturer="Ecobulles",
            model=model_from_serial_number(serial),
            sw_version=box.get("firmware_version"),
            serial_number=serial,
            connections={(CONNECTION_NETWORK_MAC, eco_ref)},
        )
        coordinators[eco_ref] = EcobullesCoordinator(hass, client, eco_ref, entry.data)

    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        )
    )
    entry.runtime_data = EcobullesRuntimeData(coordinators=coordinators)
    hass.data[DOMAIN][entry.entry_id] = {"devices": boxes}

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
