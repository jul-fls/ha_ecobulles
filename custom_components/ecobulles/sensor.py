from datetime import timedelta
import datetime
import logging

import async_timeout
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.components.sensor import SensorEntity

# import liters
from homeassistant.const import UnitOfVolume, UnitOfMass, PERCENTAGE
from homeassistant.util.dt import as_local, now as hass_now

from .const import DOMAIN
from .api import EcobullesClient


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up water usage sensor from a config entry."""
    api = EcobullesClient()
    water_and_co2_coordinator = WaterAndCo2UsageCoordinator(
        hass, api, entry.data.get("eco_ref")
    )

    eco_ref = entry.data.get("eco_ref")

    await water_and_co2_coordinator.async_config_entry_first_refresh()

    co2_bottle_weight = entry.data.get("co2_bottle_weight")
    async_add_entities(
        [
            WaterUsageSensor(water_and_co2_coordinator, eco_ref),
            CO2UsageSensor(water_and_co2_coordinator, eco_ref, co2_bottle_weight),
        ],
        True,
    )


class WaterAndCo2UsageCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching water usage data."""

    def __init__(self, hass, api, eco_ref):
        """Initialize the water usage coordinator."""
        self.api = api
        self.eco_ref = eco_ref
        super().__init__(
            hass,
            _LOGGER,
            name="Water And CO2 Usage",
            update_interval=timedelta(hours=1),
        )

    async def _async_update_data(self):
        """Fetch water usage data from the API."""
        try:
            async with async_timeout.timeout(10):
                data = await self.api.getTotalWaterAndCo2Usage(self.eco_ref, self.hass)

                last_updated_str = data.get("last_updated")
                last_updated_utc = datetime.datetime.fromisoformat(last_updated_str)
                last_updated = as_local(last_updated_utc)

                _LOGGER.warning(f"Last updated of water and co2 usage: {last_updated}")

                # Calculate how long until the next update should be scheduled
                current_time = hass_now()
                next_update_in = (
                    timedelta(hours=1)
                    - (current_time - last_updated)
                    + timedelta(minutes=1)
                )
                _LOGGER.warning(
                    f"Next update for water and co2 usage in {next_update_in}"
                )

                # Schedule next update
                self.update_interval = next_update_in
                return data
        except Exception as err:
            raise UpdateFailed(f"Error fetching water and co2 usage data: {err}")


class WaterUsageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for displaying water usage."""

    def __init__(self, coordinator, eco_ref):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.eco_ref = eco_ref
        self._attr_name = f"Water Usage"
        self._attr_unique_id = f"{eco_ref}_total_water_usage"
        self._attr_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = "water"
        self._attr_state_class = "total_increasing"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("total_eau")

    @property
    def extra_state_attributes(self):
        """Return other state attributes."""
        if self.coordinator.data is None:
            return None
        return {
            "last_updated": self.coordinator.data.get("last_updated"),
            "eco_ref": self.eco_ref,
        }

    @property
    def device_info(self):
        """Return info for linking with the correct device."""
        return {
            "identifiers": {(DOMAIN, self.eco_ref)},
            "name": f"Water Usage",
            "manufacturer": "Ecobulles",
            "model": "Ecobulles",
            # Include other relevant device info fields
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return UnitOfVolume.LITERS.value


class CO2UsageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for displaying CO2 usage."""

    def __init__(self, coordinator, eco_ref, co2_bottle_weight):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.eco_ref = eco_ref
        self.co2_bottle_weight = co2_bottle_weight
        self._attr_name = "CO2 Usage"
        self._attr_unique_id = f"{eco_ref}_co2_usage"
        self._attr_unit_of_measurement = PERCENTAGE
        self._attr_device_class = "weight"
        self.icon = "mdi:molecule-co2"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        total_gas_mg = self.coordinator.data.get("total_gas")
        if total_gas_mg is not None:
            # Assuming total_gas is in milligrams, convert to kg for 10kg bottle
            bottle_weight_in_mg = self.co2_bottle_weight * 1_000_000
            total_gas_mg = int(total_gas_mg)
            # Calculate the percentage of CO2 used from the 10Kg bottle
            percentage_used = (total_gas_mg / bottle_weight_in_mg) * 100
            return round(percentage_used, 2)
        return None

    @property
    def extra_state_attributes(self):
        """Return other state attributes."""
        if self.coordinator.data is None:
            return None
        return {
            "last_updated": self.coordinator.data.get("last_updated"),
            "eco_ref": self.eco_ref,
            # Include other relevant information if needed
        }

    @property
    def device_info(self):
        """Return info for linking with the correct device."""
        return {
            "identifiers": {(DOMAIN, self.eco_ref)},
            "name": "CO2 Usage",
            "manufacturer": "Ecobulles",
            "model": "Ecobulles",
        }
