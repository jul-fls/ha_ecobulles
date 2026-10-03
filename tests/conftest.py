"""Pytest fixtures for Ecobulles tests."""

from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest

from custom_components.ecobulles.const import (
    CONF_BOTTLE_EMPTY_CONTACT_VALUE,
    CONF_ENABLE_RAW_CO2_SENSOR,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"


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
            "email": "test@example.com",
            "password": "test-password",
            "co2_bottle_weight": 10,
            CONF_BOTTLE_EMPTY_CONTACT_VALUE: 0,
        },
        options={CONF_ENABLE_RAW_CO2_SENSOR: True},
    )
