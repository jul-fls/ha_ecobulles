"""Tests for Ecobulles diagnostics."""

from types import SimpleNamespace

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ecobulles.const import DOMAIN
from custom_components.ecobulles.diagnostics import async_get_config_entry_diagnostics

pytestmark = pytest.mark.asyncio


async def test_diagnostics_redacts_sensitive_data(hass) -> None:
    """Diagnostics redact credentials and device identifiers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "secret",
            "eco_ref": "44B7D095E9C6",
            "name": "Box",
        },
        options={"eco_ref": "44B7D095E9C6", "safe": True},
    )
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data={
                "active_alerts": [{"alert_type": "2"}],
                "total_eau": 123,
                "num_serie": "XC240007",
            }
        )
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"][CONF_EMAIL] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["eco_ref"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["name"] == "Box"
    assert diagnostics["entry"]["options"]["eco_ref"] == "**REDACTED**"
    assert diagnostics["entry"]["options"]["safe"] is True
    assert diagnostics["coordinator"]["active_alerts"] == "**REDACTED**"
    assert diagnostics["coordinator"]["num_serie"] == "**REDACTED**"
    assert diagnostics["coordinator"]["total_eau"] == 123


async def test_diagnostics_without_runtime_data(hass) -> None:
    """Diagnostics work before the coordinator exists."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})

    assert await async_get_config_entry_diagnostics(hass, entry) == {
        "entry": {"data": {}, "options": {}},
        "coordinator": {},
    }
