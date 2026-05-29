"""Focused unit tests for Ecobulles sensor internals."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ecobulles.const import (
    CONF_CO2_BOTTLE_WEIGHT_KG,
    CONF_CO2_MAX_DOSE_MG_PER_L,
    CONF_CO2_MICROMETRIC_SCREW_SETTING,
    CONF_CO2_MIN_DOSE_MG_PER_L,
    CONF_CO2_REFERENCE_PULSE_MS_PER_L,
    CONF_ENABLE_RAW_CO2_SENSOR,
    CONF_POLL_INTERVAL_SECONDS,
    DOMAIN,
)
from custom_components.ecobulles.sensor import (
    ActiveAlertsSensor,
    CO2InjectionTimeSensor,
    EcobullesCoordinator,
    EcobullesDescribedSensor,
    EstimatedCO2BottleUsageSensor,
    RAW_CO2_SENSOR,
    async_setup_entry,
)

pytestmark = pytest.mark.asyncio


def _usage(total_eau: int = 100, total_gas: int = 150_000) -> dict:
    """Return a minimal usage payload."""
    return {
        "total_eau": total_eau,
        "total_gas": total_gas,
        "last_updated": "2026-05-21T00:17:58",
    }


def _device() -> dict:
    """Return a minimal device payload."""
    return {
        "data": {
            "boite": {
                "installdate": {"date": "2024-03-28 15:15:00"},
                "lastdatereceive": "2026-05-21 21:17:58",
                "activated": "1",
                "locked": "0",
                "suspended": "0",
                "suspended_time": "0",
                "suspended_date": "2026-05-21 21:17:58",
                "firm_ver": "1.6.1",
                "last_alert": None,
                "name": "Box",
            },
            "alert": [{"currently": "0"}],
        }
    }


def _coordinator(hass, api=None, config=None) -> EcobullesCoordinator:
    """Build a coordinator with mocked API/storage."""
    return EcobullesCoordinator(
        hass,
        api
        or SimpleNamespace(
            get_total_water_and_co2_usage=AsyncMock(return_value=_usage()),
            get_device_info=AsyncMock(return_value=_device()),
            get_login_payload=AsyncMock(return_value=None),
        ),
        "eco-ref",
        config or {},
    )


async def test_sensor_setup_without_raw_debug(hass) -> None:
    """Sensor setup omits the raw debug sensor when the option is disabled."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"eco_ref": "test-eco-ref"},
        options={CONF_ENABLE_RAW_CO2_SENSOR: False},
    )
    mock_config_entry.runtime_data = SimpleNamespace(coordinator=_coordinator(hass))
    add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, add_entities)

    unique_ids = {entity.unique_id for entity in add_entities.call_args.args[0]}
    assert "test-eco-ref_raw_co2_value" not in unique_ids
    assert "test-eco-ref_co2_usage" in unique_ids
    assert "test-eco-ref_active_alerts" in unique_ids


async def test_coordinator_update_success_with_alerts_and_bottle_change(hass) -> None:
    """Coordinator merges usage, device metadata, alerts, and durable accounting."""
    api = SimpleNamespace(
        get_total_water_and_co2_usage=AsyncMock(return_value=_usage(total_eau=7)),
        get_device_info=AsyncMock(return_value=_device()),
        get_login_payload=AsyncMock(
            return_value={
                "data": {
                    "conso": {
                        "alert": [
                            {"currently": "1", "alert_type": "2"},
                            {"currently": "0", "alert_type": "3"},
                        ]
                    }
                }
            }
        ),
    )
    coordinator = _coordinator(
        hass,
        api=api,
        config={"email": "user@example.com", "password": "secret"},
    )
    coordinator._water_usage_state = None

    with (
        patch.object(
            coordinator._store,
            "async_load",
            AsyncMock(
                return_value={
                    "completed_cycles_liters": 0,
                    "cycle_water_liters": 165_000,
                    "bottle_changes": 0,
                }
            ),
        ),
        patch.object(coordinator._store, "async_save", AsyncMock()) as save_mock,
    ):
        data = await coordinator._async_update_data()

    assert data["bottle_changed"] is True
    assert data["completed_cycles_liters"] == 165_000
    assert data["cycle_water_liters"] == 7
    assert data["total_water_liters"] == 165_007
    assert data["active_alert_count"] == 1
    assert data["install_date"] == "2024-03-28T15:15:00"
    save_mock.assert_awaited_once()


async def test_coordinator_update_fails_on_incomplete_payload(hass) -> None:
    """Incomplete required API payloads mark the update as failed."""
    coordinator = _coordinator(
        hass,
        api=SimpleNamespace(
            get_total_water_and_co2_usage=AsyncMock(return_value=None),
            get_device_info=AsyncMock(return_value=_device()),
        ),
    )

    with pytest.raises(UpdateFailed, match="incomplete data"):
        await coordinator._async_update_data()


async def test_coordinator_update_wraps_timeout_and_unexpected_errors(hass) -> None:
    """Coordinator failures are normalized to UpdateFailed."""
    timeout_coordinator = _coordinator(
        hass,
        api=SimpleNamespace(
            get_total_water_and_co2_usage=AsyncMock(side_effect=TimeoutError),
            get_device_info=AsyncMock(return_value=_device()),
        ),
    )
    with pytest.raises(UpdateFailed, match="Timed out"):
        await timeout_coordinator._async_update_data()

    failing_coordinator = _coordinator(
        hass,
        api=SimpleNamespace(
            get_total_water_and_co2_usage=AsyncMock(side_effect=ValueError("boom")),
            get_device_info=AsyncMock(return_value=_device()),
        ),
    )
    with pytest.raises(UpdateFailed, match="ValueError"):
        await failing_coordinator._async_update_data()


async def test_optional_login_payload_missing_credentials_and_errors(hass) -> None:
    """Optional alert payload failures do not fail the whole update."""
    no_credentials = _coordinator(hass, config={})
    assert await no_credentials._async_fetch_login_payload() is None

    api = SimpleNamespace(get_login_payload=AsyncMock(side_effect=RuntimeError("boom")))
    with_credentials = _coordinator(
        hass,
        api=api,
        config={"email": "user@example.com", "password": "secret"},
    )
    assert await with_credentials._async_fetch_login_payload() is None


async def test_sensor_native_values_and_attributes(hass) -> None:
    """Sensor classes expose their calculated values and diagnostic attributes."""
    coordinator = _coordinator(hass)
    coordinator.async_set_updated_data(
        {
            **_usage(total_gas=1500),
            "bottle_changes": 2,
            "active_alert_count": 1,
            "active_alerts": [{"currently": "1"}],
        }
    )

    described = EcobullesDescribedSensor(coordinator, "eco-ref", RAW_CO2_SENSOR)
    assert described.native_value == 1500
    assert described.device_info == {"identifiers": {(DOMAIN, "eco-ref")}}
    assert described.extra_state_attributes["bottle_changes"] == 2

    alerts = ActiveAlertsSensor(coordinator, "eco-ref")
    assert alerts.native_value == 1
    assert alerts.extra_state_attributes["active_alerts"] == [{"currently": "1"}]

    injection_time = CO2InjectionTimeSensor(coordinator, "eco-ref")
    assert injection_time.native_value == 1.5
    assert injection_time.extra_state_attributes["raw_total_gas_ms"] == 1500


async def test_co2_injection_time_unavailable_without_raw_value(hass) -> None:
    """CO2 injection time is unavailable if the API omits total_gas."""
    coordinator = _coordinator(hass)
    coordinator.async_set_updated_data({})

    assert CO2InjectionTimeSensor(coordinator, "eco-ref").native_value is None


async def test_estimated_co2_bottle_usage_sensor(hass) -> None:
    """Estimated bottle usage exposes value and calculation assumptions."""
    coordinator = _coordinator(hass)
    coordinator.async_set_updated_data({**_usage(total_gas=900_000), "bottle_changes": 0})
    config = {
        CONF_CO2_BOTTLE_WEIGHT_KG: 10,
        CONF_CO2_MICROMETRIC_SCREW_SETTING: 5,
        CONF_CO2_MIN_DOSE_MG_PER_L: 85,
        CONF_CO2_MAX_DOSE_MG_PER_L: 150,
        CONF_CO2_REFERENCE_PULSE_MS_PER_L: 1500,
        CONF_POLL_INTERVAL_SECONDS: 120,
    }

    sensor = EstimatedCO2BottleUsageSensor(coordinator, "eco-ref", config)

    assert sensor.native_value == 0.68
    assert sensor.extra_state_attributes["estimated_dose_mg_per_l"] == 112.857
    assert sensor.extra_state_attributes["estimated_used_co2_g"] == 67.714


@pytest.mark.parametrize(
    "data, config",
    [
        ({}, {CONF_CO2_BOTTLE_WEIGHT_KG: 10}),
        ({**_usage(total_gas=1500)}, {CONF_CO2_BOTTLE_WEIGHT_KG: 0}),
        (
            {**_usage(total_gas=1500)},
            {
                CONF_CO2_BOTTLE_WEIGHT_KG: 10,
                CONF_CO2_REFERENCE_PULSE_MS_PER_L: 0,
            },
        ),
    ],
)
async def test_estimated_co2_bottle_usage_unavailable_for_invalid_inputs(
    hass, data, config
) -> None:
    """Estimated bottle usage becomes unavailable for invalid assumptions."""
    coordinator = _coordinator(hass)
    coordinator.async_set_updated_data(data)

    assert (
        EstimatedCO2BottleUsageSensor(coordinator, "eco-ref", config).native_value
        is None
    )
