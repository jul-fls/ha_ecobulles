"""Tests for durable CO2 counter accounting."""

import pytest

from custom_components.ecobulles.co2_usage import CO2UsageState


def test_counter_reset_preserves_completed_segment() -> None:
    """A device restart must not reset the estimated injection time."""
    state = CO2UsageState()

    assert state.apply(10_000) == 10_000
    assert state.apply(12_000) == 12_000
    assert state.apply(500) == 12_500
    assert state.apply(800) == 12_800
    assert state.as_dict() == {"offset_ms": 12_000, "last_raw_ms": 800}


def test_state_round_trip_and_missing_reading() -> None:
    """Stored state restores cleanly and missing readings stay unavailable."""
    state = CO2UsageState.from_dict({"offset_ms": 4_000, "last_raw_ms": 700})
    assert state.apply(None) is None
    assert state.apply(900) == 4_900


def test_negative_counter_is_rejected() -> None:
    """Negative valve-open time is invalid."""
    with pytest.raises(ValueError, match="cannot be negative"):
        CO2UsageState().apply(-1)
