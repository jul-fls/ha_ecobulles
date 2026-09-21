"""Tests for the Ecobulles bottle-empty reading."""

from custom_components.ecobulles.binary_sensor import EcobullesBottleEmptySensor
from custom_components.ecobulles.sensor import EcobullesCoordinator


def test_bottle_empty_binary_sensor(hass) -> None:
    """Missing readings are unavailable; reported empty/full states are explicit."""
    coordinator = EcobullesCoordinator(hass, None, "eco-ref", {})
    sensor = EcobullesBottleEmptySensor(coordinator, "eco-ref")
    coordinator.async_set_updated_data(
        {
            "bottle_empty": True,
            "bottle_empty_raw": 0,
            "bottle_empty_timestamp": "2026-09-21T16:18:01",
        }
    )
    assert sensor.available
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["last_reading"] == "2026-09-21T16:18:01"
    assert sensor.extra_state_attributes["raw_contact_value"] == 0
    coordinator.async_set_updated_data({"bottle_empty": False, "bottle_empty_raw": 1})
    assert sensor.available
    assert sensor.is_on is False
    assert sensor.extra_state_attributes["raw_contact_value"] == 1
    coordinator.async_set_updated_data({"bottle_empty": None})
    assert not sensor.available
    assert sensor.is_on is None
