"""Binary sensors for Ecobulles device readings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .sensor import EcobullesCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ecobulles binary sensors."""
    async_add_entities(
        [
            EcobullesBottleEmptySensor(coordinator, eco_ref)
            for eco_ref, coordinator in entry.runtime_data.coordinators.items()
        ]
    )


class EcobullesBottleEmptySensor(
    CoordinatorEntity[EcobullesCoordinator], BinarySensorEntity
):
    """Report the latest bottle-empty input from the device."""

    _attr_has_entity_name = True
    _attr_translation_key = "bottle_empty"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: EcobullesCoordinator, eco_ref: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{eco_ref}_bottle_empty"
        self._attr_device_info = {"identifiers": {(DOMAIN, eco_ref)}}

    @property
    def available(self) -> bool:
        """Avoid claiming the bottle is full if no input has been received."""
        return (
            super().available
            and self.coordinator.data.get("bottle_empty") is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the device currently reports an empty bottle."""
        return self.coordinator.data.get("bottle_empty")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose when the bottle-empty input was last reported."""
        return {
            "last_reading": self.coordinator.data.get("bottle_empty_timestamp")
        }
