"""Unit tests for small Ecobulles helper functions."""

from custom_components.ecobulles.auth_ids import generate_registration_id, generate_sand
from custom_components.ecobulles.config_flow import (
    _device_info_from_response,
    _flatten_advanced_options,
)
from custom_components.ecobulles.sensor import _active_alerts_from_payloads, _isoish


def test_generated_auth_ids_shape() -> None:
    """Generated API client identifiers have the expected broad shape."""
    assert ":APA91b" in generate_registration_id()
    assert len(generate_sand()) == 10


def test_flatten_advanced_options() -> None:
    """Advanced config-flow sections are flattened before storage."""
    assert _flatten_advanced_options({"email": "a", "advanced_options": {"x": 1}}) == {
        "email": "a",
        "x": 1,
    }


def test_device_info_from_response() -> None:
    """Device metadata is normalized from the nested API payload."""
    assert _device_info_from_response(
        {
            "data": {
                "boite": {
                    "name": "Box",
                    "installdate": {"date": "2024-01-01 00:00:00"},
                    "lastdatereceive": "2026-01-01 00:00:00",
                    "firm_ver": "1.0",
                    "num_serie": "XC",
                }
            }
        }
    ) == {
        "name": "Box",
        "install_date": "2024-01-01T00:00:00",
        "firmware_version": "1.0",
        "num_serie": "XC",
        "last_date_receive": "2026-01-01T00:00:00",
        "activated": None,
        "locked": None,
        "suspended": None,
        "suspended_time": None,
        "suspended_date": None,
        "last_alert": None,
    }


def test_sensor_helpers() -> None:
    """Sensor payload helpers keep only active alerts and normalize dates."""
    assert _isoish("2026-01-01 12:00:00") == "2026-01-01T12:00:00"
    assert _active_alerts_from_payloads(
        {"data": {"alert": [{"currently": "0"}, {"currently": "1", "id": 1}]}},
        {"data": {"conso": {"alert": [{"currently": 1, "id": 2}]}}},
    ) == [{"currently": "1", "id": 1}, {"currently": 1, "id": 2}]
