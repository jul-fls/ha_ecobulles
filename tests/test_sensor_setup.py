"""Home Assistant integration-level tests for Ecobulles sensors."""

from unittest.mock import AsyncMock, patch

from custom_components.ecobulles.const import DOMAIN


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

    assert hass.states.get("sensor.ecobulles_water_usage") is not None
    assert hass.states.get("sensor.ecobulles_water_usage_total") is not None
    assert hass.states.get("sensor.ecobulles_raw_co2_value") is not None
    assert hass.states.get("switch.ecobulles_raw_co2_debug") is not None
    assert hass.config_entries.async_entries(DOMAIN)
