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
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTime, UnitOfVolume
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util.dt import as_utc, parse_datetime

from .api import EcobullesClient
from .const import (
    CONF_CO2_BOTTLE_WEIGHT_KG,
    CONF_CO2_MAX_DOSE_MG_PER_L,
    CONF_CO2_MICROMETRIC_SCREW_SETTING,
    CONF_CO2_MIN_DOSE_MG_PER_L,
    CONF_CO2_PRESSURE_BAR,
    CONF_CO2_REFERENCE_PULSE_MS_PER_L,
    CONF_ENABLE_RAW_CO2_SENSOR,
    DOMAIN,
)
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
        CO2InjectionTimeSensor(
            coordinator,
            eco_ref,
        )
    )
    entities.append(EstimatedCO2BottleUsageSensor(coordinator, eco_ref, entry.data))
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


class CO2InjectionTimeSensor(EcobullesBaseSensor):
    """Expose the API gas counter as cumulative injection time."""

    _attr_translation_key = "co2_injection_time"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:molecule-co2"

    def __init__(
        self,
        coordinator: EcobullesCoordinator,
        eco_ref: str,
    ) -> None:
        """Initialize the CO2 injection time sensor."""
        super().__init__(coordinator, eco_ref)
        self._attr_unique_id = f"{eco_ref}_co2_usage"

    @property
    def native_value(self) -> float | None:
        """Return cumulative CO2 valve-open time in seconds."""
        total_gas = self.coordinator.data.get("total_gas")
        if total_gas is None:
            return None
        return round(int(total_gas) / 1000, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the original raw millisecond counter."""
        return {
            **super().extra_state_attributes,
            "raw_total_gas_ms": self.coordinator.data.get("total_gas"),
            "interpretation": "cumulative CO2 electrovalve open time",
        }


class EstimatedCO2BottleUsageSensor(EcobullesBaseSensor):
    """Estimate bottle usage from injection time and Ecobulles dose guidance."""

    _attr_translation_key = "estimated_co2_bottle_usage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:gauge"

    def __init__(
        self,
        coordinator: EcobullesCoordinator,
        eco_ref: str,
        config: dict[str, Any],
    ) -> None:
        """Initialize the estimated CO2 bottle usage sensor."""
        super().__init__(coordinator, eco_ref)
        self.config = config
        self._attr_unique_id = f"{eco_ref}_estimated_co2_bottle_usage"

    @property
    def native_value(self) -> float | None:
        """Return estimated bottle usage percentage."""
        total_gas = self.coordinator.data.get("total_gas")
        flow_rate = self._estimated_flow_rate_g_per_min
        bottle_weight_kg = float(self.config.get(CONF_CO2_BOTTLE_WEIGHT_KG, 10) or 10)
        if total_gas is None or flow_rate <= 0 or bottle_weight_kg <= 0:
            return None

        open_minutes = int(total_gas) / 1000 / 60
        used_grams = open_minutes * flow_rate
        return round((used_grams / (bottle_weight_kg * 1000)) * 100, 2)

    @property
    def _estimated_flow_rate_g_per_min(self) -> float:
        """Estimate active-valve CO2 flow in g/min.

        Ecobulles indicates that a 10 kg CO2 bottle treats about 60-120 m3 or
        80-120 m3 depending on the page, implying a practical middle range of
        roughly 85-150 mg/L. The
        micrometric screw is mapped linearly from setting 2 to 9 across that
        range. With the observed/default 1500 ms pulse per liter, this gives:

            g/min = dose_mg_per_l / pulse_ms_per_l * 60
        """
        dose = self._estimated_dose_mg_per_l
        pulse_ms = float(
            self.config.get(CONF_CO2_REFERENCE_PULSE_MS_PER_L, 1500) or 1500
        )
        if dose <= 0 or pulse_ms <= 0:
            return 0
        return dose / pulse_ms * 60

    @property
    def _estimated_dose_mg_per_l(self) -> float:
        """Estimate CO2 dose in mg/L from the micrometric screw setting."""
        screw = float(self.config.get(CONF_CO2_MICROMETRIC_SCREW_SETTING, 5) or 5)
        min_dose = float(self.config.get(CONF_CO2_MIN_DOSE_MG_PER_L, 85) or 85)
        max_dose = float(self.config.get(CONF_CO2_MAX_DOSE_MG_PER_L, 150) or 150)
        normalized_screw = min(max(screw, 2), 9)
        return min_dose + ((normalized_screw - 2) / 7) * (max_dose - min_dose)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the assumptions used by the estimate."""
        total_gas = self.coordinator.data.get("total_gas") or 0
        flow_rate = self._estimated_flow_rate_g_per_min
        open_minutes = int(total_gas) / 1000 / 60
        return {
            **super().extra_state_attributes,
            "co2_bottle_weight_kg": self.config.get(CONF_CO2_BOTTLE_WEIGHT_KG, 10),
            "micrometric_screw_setting": self.config.get(
                CONF_CO2_MICROMETRIC_SCREW_SETTING, 5
            ),
            "co2_pressure_bar": self.config.get(CONF_CO2_PRESSURE_BAR, 5),
            "estimated_dose_mg_per_l": round(self._estimated_dose_mg_per_l, 3),
            "reference_pulse_ms_per_l": self.config.get(
                CONF_CO2_REFERENCE_PULSE_MS_PER_L, 1500
            ),
            "estimated_flow_rate_g_per_min": round(flow_rate, 6),
            "estimated_used_co2_g": round(open_minutes * flow_rate, 3),
            "calculation_model": "linear screw setting 2-9 mapped to 85-150 mg/L, using reference pulse ms/L",
            "warning": (
                "Estimate uses Ecobulles public dose range and is not a measured bottle calibration."
            ),
        }
