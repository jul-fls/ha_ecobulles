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
    try:
        api = EcobullesClient()
        eco_ref = entry.data.get("eco_ref")
        co2_bottle_weight = entry.data.get("co2_bottle_weight")

        coordinator = WaterAndCo2UsageCoordinator(hass, api, eco_ref)

        try:
            await coordinator.async_config_entry_first_refresh()
        except Exception as e:
            _LOGGER.error("Erreur lors du premier rafraîchissement de données Ecobulles: %s", e)
            return

        async_add_entities([
            WaterUsageSensor(coordinator, eco_ref),
            CO2UsageSensor(coordinator, eco_ref, co2_bottle_weight),
            InstallDateSensor(coordinator, eco_ref),
            LastDateReceiveSensor(coordinator, eco_ref),
            ActivatedSensor(coordinator, eco_ref),
            LockedSensor(coordinator, eco_ref),
            ActivatedSensor(coordinator, eco_ref),
            SuspendedSensor(coordinator, eco_ref),
        ], True)
    except Exception as outer:
        _LOGGER.exception("Erreur lors de l'installation des capteurs Ecobulles: %s", outer)
        return



class WaterAndCo2UsageCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching water usage data."""

    def __init__(self, hass, api, eco_ref):
        """Initialize the water usage coordinator."""
        self.api = api
        self.eco_ref = eco_ref
        super().__init__(
            hass,
            _LOGGER,
            name="Ecobulles {self.name}",
            update_interval=timedelta(hours=1),
        )

    async def _async_update_data(self):
        """Fetch water usage data from the API."""
        try:
            async with async_timeout.timeout(10):
                data1 = await self.api.getTotalWaterAndCo2Usage(self.eco_ref, self.hass)
                data2 = await self.api.getDeviceInfo(self.eco_ref)
                data = {
                    **data1,
                    "install_date": data2.get("data", {}).get("boite", {}).get("installdate", {}).get("date").replace(" ", "T"),
                    "last_date_receive": data2.get("data", {}).get("boite", {}).get("lastdatereceive"),
                    "activated": data2.get("data", {}).get("boite", {}).get("activated"),
                    "locked": data2.get("data", {}).get("boite", {}).get("locked"),
                    "suspended": data2.get("data", {}).get("boite", {}).get("suspended"),
                    "suspended_time": data2.get("data").get("boite").get("suspended_time"),
                    "suspended_date": (data2.get("data").get("boite").get("suspended_date")).replace(" ", "T"),
                    "firm_ver": data2.get("data", {}).get("boite", {}).get("firm_ver"),
                    "last_alert": data2.get("data").get("boite").get("last_alert"),
                    "name": data2.get("data", {}).get("boite", {}).get("name"),
                }

                if not data:
                    _LOGGER.warning("Aucune donnée reçue depuis l’API pour l’utilisation de l’eau et du CO2.")
                    return None

                return data

        except Exception as err:
            raise UpdateFailed(f"Error fetching water and co2 usage data: {err}")


class WaterUsageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for displaying water usage."""

    def __init__(self, coordinator, eco_ref):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.eco_ref = eco_ref
        self._attr_name = f"Ecobulles Water Usage"
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
        self._attr_name = "Ecobulles CO2 Usage"
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
        }

class InstallDateSensor(CoordinatorEntity, SensorEntity):
    """Sensor for displaying the installation date of the ecobulles system"""
    def __init__(self, coordinator, eco_ref: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.eco_ref = eco_ref
        self._attr_name = "Ecobulles Install Date"
        self._attr_unique_id = f"{eco_ref}_install_date"
        self._attr_device_class = "date"
        self._state = self.coordinator.data.get("install_date")
        self.icon = "mdi:calendar"

    @property
    def state(self):
        return self._state
    
    @property
    def device_info(self):
        """Return info for linking with the correct device."""
        return {
            "identifiers": {(DOMAIN, self.eco_ref)},
        }

class LastDateReceiveSensor(CoordinatorEntity, SensorEntity):
    """Sensor for displaying the last date receive of the ecobulles system"""
    def __init__(self, coordinator, eco_ref: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.eco_ref = eco_ref
        self._attr_name = "Ecobulles Last Date Receive"
        self._attr_unique_id = f"{eco_ref}_last_date_receive"
        self._attr_device_class = "date"
        self._state = self.coordinator.data.get("last_date_receive")
        self.icon = "mdi:calendar"

    @property
    def state(self):
        return self._state
    
    @property
    def device_info(self):
        """Return info for linking with the correct device."""
        return {
            "identifiers": {(DOMAIN, self.eco_ref)},
        }

class ActivatedSensor(CoordinatorEntity, SensorEntity):
    """Sensor for displaying the activated status of the ecobulles system"""
    def __init__(self, coordinator, eco_ref: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.eco_ref = eco_ref
        self._attr_name = "Ecobulles Activated"
        self._attr_unique_id = f"{eco_ref}_activated"
        self._attr_device_class = "boolean"
        self._state = self.coordinator.data.get("activated")
        self.icon = "mdi:check-circle"

    @property
    def state(self):
        return self._state
    
    @property
    def device_info(self):
        """Return info for linking with the correct device."""
        return {
            "identifiers": {(DOMAIN, self.eco_ref)},
        }


class LockedSensor(CoordinatorEntity, SensorEntity):
    """Sensor for displaying the locked status of the ecobulles system"""
    def __init__(self, coordinator, eco_ref: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.eco_ref = eco_ref
        self._attr_name = "Ecobulles Locked"
        self._attr_unique_id = f"{eco_ref}_locked"
        self._attr_device_class = "boolean"
        self._state = self.coordinator.data.get("locked")
        self.icon = "mdi:check-circle"

    @property
    def state(self):
        return self._state
    
    @property
    def device_info(self):
        """Return info for linking with the correct device."""
        return {
            "identifiers": {(DOMAIN, self.eco_ref)},
        }

class SuspendedSensor(CoordinatorEntity, SensorEntity):
    """Sensor for displaying the suspended status of the ecobulles system"""
    def __init__(self, coordinator, eco_ref: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.eco_ref = eco_ref
        self._attr_name = "Ecobulles Suspended"
        self._attr_unique_id = f"{eco_ref}_suspended"
        self._attr_device_class = "boolean"
        self._state = self.coordinator.data.get("suspended")
        self.icon = "mdi:check-circle"

    @property
    def state(self):
        return self._state
    
    @property
    def device_info(self):
        """Return info for linking with the correct device."""
        return {
            "identifiers": {(DOMAIN, self.eco_ref)},
        }