"""Tests for Ecobulles switches."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ecobulles.const import CONF_ENABLE_RAW_CO2_SENSOR, DOMAIN
from custom_components.ecobulles.switch import RawCO2DebugSwitch, async_setup_entry

pytestmark = pytest.mark.asyncio


async def test_switch_setup_adds_debug_switch(hass, mock_config_entry) -> None:
    """Switch setup registers the raw CO2 debug switch."""
    add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, add_entities)

    add_entities.assert_called_once()
    entity = add_entities.call_args.args[0][0]
    assert isinstance(entity, RawCO2DebugSwitch)


async def test_raw_co2_debug_switch_updates_option(hass, mock_config_entry) -> None:
    """The debug switch persists its option and reloads the entry."""
    mock_config_entry.add_to_hass(hass)
    switch = RawCO2DebugSwitch(hass, mock_config_entry)
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()

    assert switch.is_on is True
    assert switch.device_info == {"identifiers": {(DOMAIN, "test-eco-ref")}}

    with patch.object(
        hass.config_entries,
        "async_reload",
        AsyncMock(return_value=True),
    ) as reload_mock:
        await switch.async_turn_off()

    assert mock_config_entry.options[CONF_ENABLE_RAW_CO2_SENSOR] is False
    switch.async_write_ha_state.assert_called_once()
    reload_mock.assert_awaited_once_with(mock_config_entry.entry_id)

    with patch.object(
        hass.config_entries,
        "async_reload",
        AsyncMock(return_value=True),
    ):
        await switch.async_turn_on()

    assert mock_config_entry.options[CONF_ENABLE_RAW_CO2_SENSOR] is True
