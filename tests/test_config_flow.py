"""Tests for the Ecobulles config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ecobulles.config_flow import CannotConnect
from custom_components.ecobulles.const import (
    CONF_CO2_BOTTLE_WEIGHT_KG,
    CONF_CO2_MICROMETRIC_SCREW_SETTING,
    DOMAIN,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


USER_INPUT = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "secret",
    CONF_CO2_BOTTLE_WEIGHT_KG: 10,
    CONF_CO2_MICROMETRIC_SCREW_SETTING: 5,
}

FLOW_INFO = {
    "title": "Ecobulles : Test box",
    "user_id": "user-id",
    "eco_ref": "test-eco-ref",
}

DEVICE_INFO = {
    "data": {
        "boite": {
            "name": "Test box",
            "firm_ver": "1.0",
            "num_serie": "XC240007",
            "installdate": {"date": "2024-01-01 00:00:00"},
            "lastdatereceive": "2026-01-01 00:00:00",
        }
    }
}


async def test_user_flow_creates_entry(hass) -> None:
    """Successful setup creates a config entry."""
    with (
        patch(
            "custom_components.ecobulles.config_flow.validate_input",
            AsyncMock(return_value=FLOW_INFO),
        ),
        patch(
            "custom_components.ecobulles.config_flow.EcobullesClient.get_device_info",
            AsyncMock(return_value=DEVICE_INFO),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == config_entries.FlowResultType.CREATE_ENTRY
    assert result["title"] == FLOW_INFO["title"]
    assert result["data"]["eco_ref"] == "test-eco-ref"


async def test_user_flow_handles_connection_error(hass) -> None:
    """Connection errors are surfaced on the form."""
    with patch(
        "custom_components.ecobulles.config_flow.validate_input",
        AsyncMock(side_effect=CannotConnect()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == config_entries.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_rejects_different_device(hass, mock_config_entry) -> None:
    """Reauthentication must not silently switch to another Ecobulles device."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.ecobulles.config_flow.validate_input",
        AsyncMock(return_value={**FLOW_INFO, "eco_ref": "another-eco-ref"}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "new-secret",
            },
        )

    assert result["type"] == config_entries.FlowResultType.FORM
    assert result["errors"] == {"base": "different_device"}


@pytest.fixture
def configured_entry() -> MockConfigEntry:
    """Return a configured Ecobulles entry."""
    return MockConfigEntry(domain=DOMAIN, data={**USER_INPUT, "eco_ref": "test-eco-ref"})
