"""Sensor platform for Ecobulles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Callable

import async_timeout
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfVolume
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util.dt import as_utc, parse_datetime

from .api import EcobullesClient
from .const import CONF_ENABLE_RAW_CO2_SENSOR, DOMAIN
from .water_usage import WaterUsageState

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1


@dataclass(frozen=True, kw_only=True)
class EcobullesSensorDescription(SensorEntityDescription):
    """Describe an Ecobulles sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


WATER_SENSORS: tuple[EcobullesSensorDescription, ...] = (
    EcobullesSensorDescription(
        key="total_water_usage",
        translation_key="total_water_usage",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data["cycle_water_liters"],
    ),
    EcobullesSensorDescription(
        key="water_usage_completed_bottles",
        translation_key="water_usage_completed_bottles",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["completed_cycles_liters"],
    ),
    EcobullesSensorDescription(
        key="water_usage_total",
        translation_key="water_usage_total",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["total_water_liters"],
    ),
)

RAW_CO2_SENSOR = EcobullesSensorDescription(
    key="raw_co2_value",
    translation_key="raw_co2_value",
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda data: data.get("total_gas"),
)

DIAGNOSTIC_SENSORS: tuple[EcobullesSensorDescription, ...] = (
    EcobullesSensorDescription(
        key="install_date",
        translation_key="install_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _parse_timestamp(data.get("install_date")),
    ),
    EcobullesSensorDescription(
        key="last_date_receive",
        translation_key="last_date_receive",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _parse_timestamp(data.get("last_date_receive")),
    ),
    EcobullesSensorDescription(
        key="activated",
        translation_key="activated",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("activated"),
    ),
    EcobullesSensorDescription(
        key="locked",
        translation_key="locked",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("locked"),
    ),
    EcobullesSensorDescription(
        key="suspended",
        translation_key="suspended",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("suspended"),
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Ecobulles sensors from a config entry."""
    eco_ref = entry.data["eco_ref"]
    coordinator = EcobullesCoordinator(
        hass,
        EcobullesClient(hass),
        eco_ref,
    )
    await coordinator.async_config_entry_first_refresh()

    entities: list[SensorEntity] = [
        EcobullesDescribedSensor(coordinator, eco_ref, description)
        for description in (*WATER_SENSORS, *DIAGNOSTIC_SENSORS)
    ]
    if entry.options.get(CONF_ENABLE_RAW_CO2_SENSOR, False):
        entities.append(EcobullesDescribedSensor(coordinator, eco_ref, RAW_CO2_SENSOR))
    entities.append(
        CO2UsageSensor(
            coordinator,
            eco_ref,
            entry.data.get("co2_bottle_weight", 10),
        )
    )
    async_add_entities(entities)


class EcobullesCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch API data and own durable Ecobulles accounting state."""

    def __init__(self, hass, api: EcobullesClient, eco_ref: str) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.eco_ref = eco_ref
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{eco_ref}.water_usage")
        self._water_usage_state: WaterUsageState | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=f"Ecobulles {eco_ref}",
            update_interval=timedelta(minutes=1),
        )

    async def _load_water_usage_state(self) -> WaterUsageState:
        """Load durable water accounting once."""
        if self._water_usage_state is None:
            self._water_usage_state = WaterUsageState.from_dict(await self._store.async_load())
        return self._water_usage_state

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch Ecobulles data and update cumulative water accounting."""
        try:
            async with async_timeout.timeout(10):
                usage = await self.api.get_total_water_and_co2_usage(self.eco_ref)
                device = await self.api.get_device_info(self.eco_ref)
        except Exception as err:
            raise UpdateFailed(f"Error fetching Ecobulles data: {err}") from err

        if usage is None or device is None:
            raise UpdateFailed("Ecobulles API returned incomplete data")

        box = device.get("data", {}).get("boite", {})
        water_state = await self._load_water_usage_state()
        bottle_changed = water_state.apply_cycle_value(usage["total_eau"])
        await self._store.async_save(water_state.as_dict())

        if bottle_changed:
            _LOGGER.info(
                "Detected CO2 bottle change for %s; closed cycle at %s L",
                self.eco_ref,
                water_state.completed_cycles_liters,
            )

        return {
            **usage,
            **water_state.as_dict(),
            "total_water_liters": water_state.total_water_liters,
            "bottle_changed": bottle_changed,
            "install_date": _isoish(box.get("installdate", {}).get("date")),
            "last_date_receive": _isoish(box.get("lastdatereceive")),
            "activated": box.get("activated"),
            "locked": box.get("locked"),
            "suspended": box.get("suspended"),
            "suspended_time": box.get("suspended_time"),
            "suspended_date": _isoish(box.get("suspended_date")),
            "firm_ver": box.get("firm_ver"),
            "last_alert": box.get("last_alert"),
            "name": box.get("name"),
        }


def _isoish(value: str | None) -> str | None:
    """Normalize API date strings without exploding on missing values."""
    return value.replace(" ", "T") if value else None


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an API timestamp string for Home Assistant's timestamp device class."""
    parsed = parse_datetime(value) if value else None
    return as_utc(parsed) if parsed else None




class EcobullesBaseSensor(CoordinatorEntity[EcobullesCoordinator], SensorEntity):
    """Base Ecobulles sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EcobullesCoordinator, eco_ref: str) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self.eco_ref = eco_ref

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device registry metadata."""
        return {"identifiers": {(DOMAIN, self.eco_ref)}}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose useful shared metadata."""
        return {
            "eco_ref": self.eco_ref,
            "last_updated": self.coordinator.data.get("last_updated"),
            "bottle_changes": self.coordinator.data.get("bottle_changes"),
        }


class EcobullesDescribedSensor(EcobullesBaseSensor):
    """Generic sensor backed by an entity description."""

    entity_description: EcobullesSensorDescription

    def __init__(
        self,
        coordinator: EcobullesCoordinator,
        eco_ref: str,
        description: EcobullesSensorDescription,
    ) -> None:
        """Initialize a described sensor."""
        super().__init__(coordinator, eco_ref)
        self.entity_description = description
        self._attr_unique_id = f"{eco_ref}_{description.key}"

    @property
    def native_value(self):
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class CO2UsageSensor(EcobullesBaseSensor):
    """Expose the raw API gas counter as a bottle-relative percentage estimate."""

    _attr_translation_key = "co2_usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:molecule-co2"

    def __init__(
        self,
        coordinator: EcobullesCoordinator,
        eco_ref: str,
        co2_bottle_weight: int,
    ) -> None:
        """Initialize the CO2 usage sensor."""
        super().__init__(coordinator, eco_ref)
        self.co2_bottle_weight = co2_bottle_weight
        self._attr_unique_id = f"{eco_ref}_co2_usage"

    @property
    def native_value(self) -> float | None:
        """Return the estimated consumed fraction of the configured bottle."""
        total_gas = self.coordinator.data.get("total_gas")
        if total_gas is None:
            return None
        bottle_weight_in_mg = self.co2_bottle_weight * 1_000_000
        return round((int(total_gas) / bottle_weight_in_mg) * 100, 2)
