"""Home Assistant integration-level tests for Ecobulles sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.ecobulles.const import DOMAIN

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


async def test_sensor_setup_with_raw_co2_debug_enabled(hass, mock_config_entry) -> None:
    """The integration loads its entities without talking to the real cloud."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.ecobulles.sensor.EcobullesClient.get_total_water_and_co2_usage",
            AsyncMock(
                return_value={
                    "total_gas": 35_464_000,
                    "total_eau": 161_649,
                    "last_updated": "2025-06-05T21:50:00",
                }
            ),
        ),
        patch(
            "custom_components.ecobulles.sensor.EcobullesClient.get_device_info",
            AsyncMock(
                return_value={
                    "data": {
                        "boite": {
                            "installdate": {"date": "2024-01-01 00:00:00"},
                            "lastdatereceive": "2025-06-05 21:50:00",
                            "activated": True,
                            "locked": False,
                            "suspended": False,
                            "suspended_time": None,
                            "suspended_date": None,
                            "firm_ver": "1.0",
                            "last_alert": None,
                            "name": "Test box",
                        }
                    }
                }
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    water_usage_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "test-eco-ref_total_water_usage"
    )
    total_water_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "test-eco-ref_water_usage_total"
    )
    raw_co2_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "test-eco-ref_raw_co2_value"
    )
    install_date_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "test-eco-ref_install_date"
    )
    last_receive_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "test-eco-ref_last_date_receive"
    )
    raw_debug_switch_entity_id = registry.async_get_entity_id(
        "switch", DOMAIN, "test-eco-ref_raw_co2_debug"
    )

    assert water_usage_entity_id is not None
    assert total_water_entity_id is not None
    assert raw_co2_entity_id is not None
    assert install_date_entity_id is not None
    assert last_receive_entity_id is not None
    assert raw_debug_switch_entity_id is not None

    assert hass.states[install_date_entity_id].state == "2024-01-01"
    assert hass.states[last_receive_entity_id].state == "2025-06-05T21:50:00"
    assert hass.config_entries.async_entries(DOMAIN)
