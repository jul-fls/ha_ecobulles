"""Config flow for Ecobulles integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import EcobullesClient

from .const import CONF_ENABLE_RAW_CO2_SENSOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required("co2_bottle_weight", default=10): int,
        # vol.Required("co2_injection_rate", default=10): int,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    # Create an instance of your API client

    # Try to authenticate with the provided credentials
    client = EcobullesClient(hass)
    auth_success, user_id, eco_ref, boitier_name = await client.authenticate(
        data[CONF_EMAIL], data[CONF_PASSWORD]
    )
    if auth_success:
        # Authentication was successful
        return {
            "title": "Ecobulles : " + boitier_name,
            "user_id": user_id,
            "eco_ref": eco_ref,
        }
    else:
        # Authentication failed
        raise InvalidAuth


def _device_info_from_response(device_info_raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize the nested device payload stored in the config entry."""
    box = device_info_raw.get("data", {}).get("boite", {})
    return {
        "name": box.get("name"),
        "install_date": _isoish(box.get("installdate", {}).get("date")),
        "firmware_version": box.get("firm_ver"),
        "num_serie": box.get("num_serie"),
        "last_date_receive": _isoish(box.get("lastdatereceive")),
        "activated": box.get("activated"),
        "locked": box.get("locked"),
        "suspended": box.get("suspended"),
        "suspended_time": box.get("suspended_time"),
        "suspended_date": _isoish(box.get("suspended_date")),
        "last_alert": box.get("last_alert"),
    }


def _isoish(value: str | None) -> str | None:
    """Normalize the API's date-ish strings."""
    return value.replace(" ", "T") if value else None


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecobulles."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if info["title"]:
                    client = EcobullesClient(self.hass)
                    device_info_raw = await client.get_device_info(info["eco_ref"])
                    entry_data = {
                        **user_input,
                        **info,
                        **_device_info_from_response(device_info_raw or {}),
                    }
                    # Ensure you're not storing 'title' in the entry data, as it was used just for entry naming
                    entry_data.pop("title", None)

                    existing_entry = await self.async_set_unique_id(
                        user_input[CONF_EMAIL]
                    )
                    if existing_entry:
                        self.hass.config_entries.async_update_entry(
                            existing_entry, data=entry_data
                        )
                        await self.hass.config_entries.async_reload(
                            existing_entry.entry_id
                        )
                        return self.async_abort(reason="reconfigured")
                    return self.async_create_entry(title=info["title"], data=entry_data)
                else:
                    errors["base"] = "auth"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class OptionsFlowHandler(OptionsFlowWithConfigEntry):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Validate user input
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if info["title"]:
                    client = EcobullesClient(self.hass)
                    device_info_raw = await client.get_device_info(info["eco_ref"])
                    entry_data = {
                        **user_input,
                        **info,
                        **_device_info_from_response(device_info_raw or {}),
                    }
                    # Ensure you're not storing 'title' in the entry data, as it was used just for entry naming
                    entry_data.pop("title", None)
                    # Update config entry with new data if validation is successful
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=entry_data
                    )
                    # Optionally, you might want to reload the integration to apply changes
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )
                    return self.async_create_entry(
                        title="", data=None
                    )  # No need to return data for options
                else:
                    # If validation fails, show an error on the form
                    errors["base"] = "invalid_auth"

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_EMAIL, default=self.config_entry.data[CONF_EMAIL]
                ): str,
                vol.Required(
                    CONF_PASSWORD, default=self.config_entry.data[CONF_PASSWORD]
                ): str,
                vol.Required(
                    "co2_bottle_weight",
                    default=self.config_entry.data["co2_bottle_weight"],
                ): int,
                vol.Optional(
                    CONF_ENABLE_RAW_CO2_SENSOR,
                    default=self.config_entry.options.get(
                        CONF_ENABLE_RAW_CO2_SENSOR, False
                    ),
                ): bool,
                # vol.Reqquired(
                #     "co2_injection_rate",
                #     default=self.config_entry.data["co2_injection_rate"],
                # ): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=options_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
