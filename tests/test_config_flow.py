"""Tests for the Ecobulles config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ecobulles.config_flow import CannotConnect, InvalidAuth
from custom_components.ecobulles.const import (
    CONF_CO2_BOTTLE_WEIGHT_KG,
    CONF_CO2_MICROMETRIC_SCREW_SETTING,
    CONF_ENABLE_RAW_CO2_SENSOR,
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
        patch(
            "custom_components.ecobulles.async_setup_entry",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
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

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_handles_invalid_auth(hass) -> None:
    """Invalid auth is surfaced on the form."""
    with patch(
        "custom_components.ecobulles.config_flow.validate_input",
        AsyncMock(side_effect=InvalidAuth()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_handles_unknown_error(hass) -> None:
    """Unexpected validation errors are surfaced on the form."""
    with patch(
        "custom_components.ecobulles.config_flow.validate_input",
        AsyncMock(side_effect=ValueError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_reconfigures_existing_entry(hass) -> None:
    """Adding an already-known device updates and reloads the existing entry."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**USER_INPUT, "eco_ref": "test-eco-ref"},
        unique_id="test-eco-ref",
    )
    existing_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.ecobulles.config_flow.validate_input",
            AsyncMock(return_value=FLOW_INFO),
        ),
        patch(
            "custom_components.ecobulles.config_flow.EcobullesClient.get_device_info",
            AsyncMock(return_value=DEVICE_INFO),
        ),
        patch.object(
            hass.config_entries,
            "async_reload",
            AsyncMock(return_value=True),
        ) as reload_mock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigured"
    assert existing_entry.data["eco_ref"] == "test-eco-ref"
    reload_mock.assert_awaited_once_with(existing_entry.entry_id)


async def test_user_flow_handles_missing_title(hass) -> None:
    """Unexpected empty titles keep the setup form open."""
    with patch(
        "custom_components.ecobulles.config_flow.validate_input",
        AsyncMock(return_value={**FLOW_INFO, "title": ""}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "auth"}


async def test_user_flow_without_input_shows_form(hass) -> None:
    """The first user step shows a form before credentials are submitted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_validate_input_normalizes_success(hass) -> None:
    """validate_input returns normalized metadata after authentication."""
    from custom_components.ecobulles.config_flow import validate_input

    with patch(
        "custom_components.ecobulles.config_flow.EcobullesClient.authenticate",
        AsyncMock(return_value=(True, "user-id", "eco-ref", "Box")),
    ):
        assert await validate_input(hass, USER_INPUT) == {
            "title": "Ecobulles : Box",
            "user_id": "user-id",
            "eco_ref": "eco-ref",
        }


async def test_validate_input_maps_runtime_errors(hass) -> None:
    """Low-level API runtime errors become cannot-connect errors."""
    from custom_components.ecobulles.config_flow import validate_input

    with patch(
        "custom_components.ecobulles.config_flow.EcobullesClient.authenticate",
        AsyncMock(side_effect=RuntimeError("network")),
    ):
        with pytest.raises(CannotConnect):
            await validate_input(hass, USER_INPUT)


async def test_validate_input_maps_timeout_errors(hass) -> None:
    """Low-level API timeouts become cannot-connect errors."""
    from custom_components.ecobulles.config_flow import validate_input

    with patch(
        "custom_components.ecobulles.config_flow.EcobullesClient.authenticate",
        AsyncMock(side_effect=TimeoutError),
    ):
        with pytest.raises(CannotConnect):
            await validate_input(hass, USER_INPUT)


async def test_validate_input_rejects_invalid_auth(hass) -> None:
    """Authentication failures become invalid-auth errors."""
    from custom_components.ecobulles.config_flow import validate_input

    with patch(
        "custom_components.ecobulles.config_flow.EcobullesClient.authenticate",
        AsyncMock(return_value=(False, None, None, None)),
    ):
        with pytest.raises(InvalidAuth):
            await validate_input(hass, USER_INPUT)


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

    assert result["type"] == "form"
    assert result["errors"] == {"base": "different_device"}


async def test_reauth_updates_credentials_for_same_device(
    hass, mock_config_entry
) -> None:
    """Successful reauthentication updates the stored credentials."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.ecobulles.config_flow.validate_input",
            AsyncMock(return_value=FLOW_INFO),
        ),
        patch.object(
            hass.config_entries,
            "async_reload",
            AsyncMock(return_value=True),
        ),
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

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-secret"


@pytest.mark.parametrize(
    ("exception", "error"),
    [(CannotConnect(), "cannot_connect"), (InvalidAuth(), "invalid_auth")],
)
async def test_reauth_handles_validation_errors(
    hass, mock_config_entry, exception, error
) -> None:
    """Reauth keeps the form open on validation errors."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.ecobulles.config_flow.validate_input",
        AsyncMock(side_effect=exception),
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

    assert result["type"] == "form"
    assert result["errors"] == {"base": error}


async def test_reauth_unknown_entry_aborts(hass) -> None:
    """Reauth aborts if Home Assistant no longer has the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": "missing-entry",
        },
        data=USER_INPUT,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


async def test_reconfigure_rejects_different_device(hass, mock_config_entry) -> None:
    """Reconfigure cannot silently switch to another Ecobulles device."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.ecobulles.config_flow.validate_input",
        AsyncMock(return_value={**FLOW_INFO, "eco_ref": "another-eco-ref"}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": mock_config_entry.entry_id,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "different_device"}


async def test_reconfigure_unknown_entry_aborts(hass) -> None:
    """Reconfigure aborts if Home Assistant no longer has the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": "missing-entry",
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


@pytest.mark.parametrize(
    ("exception", "error"),
    [(CannotConnect(), "cannot_connect"), (InvalidAuth(), "invalid_auth")],
)
async def test_reconfigure_handles_validation_errors(
    hass, mock_config_entry, exception, error
) -> None:
    """Reconfigure keeps the form open on validation errors."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.ecobulles.config_flow.validate_input",
        AsyncMock(side_effect=exception),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": mock_config_entry.entry_id,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": error}


async def test_reconfigure_updates_entry(hass, mock_config_entry) -> None:
    """Successful reconfigure updates entry data and title."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.ecobulles.config_flow.validate_input",
            AsyncMock(return_value=FLOW_INFO),
        ),
        patch(
            "custom_components.ecobulles.config_flow.EcobullesClient.get_device_info",
            AsyncMock(return_value=DEVICE_INFO),
        ),
        patch.object(
            hass.config_entries,
            "async_reload",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": mock_config_entry.entry_id,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**USER_INPUT, CONF_CO2_BOTTLE_WEIGHT_KG: 12},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_CO2_BOTTLE_WEIGHT_KG] == 12
    assert mock_config_entry.title == FLOW_INFO["title"]


async def test_options_flow_updates_data_and_options(
    hass, mock_config_entry
) -> None:
    """Options flow updates config data and the raw debug option."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.ecobulles.config_flow.validate_input",
            AsyncMock(return_value=FLOW_INFO),
        ),
        patch(
            "custom_components.ecobulles.config_flow.EcobullesClient.get_device_info",
            AsyncMock(return_value=DEVICE_INFO),
        ),
        patch.object(
            hass.config_entries,
            "async_reload",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                **USER_INPUT,
                CONF_ENABLE_RAW_CO2_SENSOR: True,
            },
        )

    assert result["type"] == "create_entry"
    assert mock_config_entry.options[CONF_ENABLE_RAW_CO2_SENSOR] is True


async def test_options_flow_handles_connection_error(
    hass, mock_config_entry
) -> None:
    """Options flow keeps the form open on connection errors."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.ecobulles.config_flow.validate_input",
        AsyncMock(side_effect=CannotConnect()),
    ):
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result.get("errors") in (None, {"base": "cannot_connect"})


async def test_options_flow_handles_invalid_auth(hass, mock_config_entry) -> None:
    """Options flow keeps the form open on invalid auth."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.ecobulles.config_flow.validate_input",
        AsyncMock(side_effect=InvalidAuth()),
    ):
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result.get("errors") in (None, {"base": "invalid_auth"})


async def test_options_flow_handles_unknown_error(hass, mock_config_entry) -> None:
    """Options flow keeps the form open on unexpected errors."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.ecobulles.config_flow.validate_input",
        AsyncMock(side_effect=ValueError("boom")),
    ):
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=USER_INPUT,
        )

    assert result["type"] == "form"
    assert result.get("errors") in (None, {"base": "unknown"})


@pytest.fixture
def configured_entry() -> MockConfigEntry:
    """Return a configured Ecobulles entry."""
    return MockConfigEntry(domain=DOMAIN, data={**USER_INPUT, "eco_ref": "test-eco-ref"})
