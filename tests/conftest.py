"""Pytest fixtures for Ecobulles tests."""

from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest

from custom_components.ecobulles.const import CONF_ENABLE_RAW_CO2_SENSOR, DOMAIN


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "eco_ref": "test-eco-ref",
            "name": "Test box",
            "num_serie": "SERIAL",
            "firmware_version": "1.0",
            "co2_bottle_weight": 10,
        },
        options={CONF_ENABLE_RAW_CO2_SENSOR: True},
    )
