"""Tests for durable water accounting."""

from custom_components.ecobulles.water_usage import WaterUsageState


def test_counter_reset_keeps_total_monotonic_without_claiming_bottle_change() -> None:
    """A lower counter preserves totals without assigning a cause."""
    state = WaterUsageState()

    assert state.apply_cycle_value(161_649) is False
    assert state.apply_cycle_value(165_894) is False
    assert state.apply_cycle_value(7) is True

    assert state.completed_cycles_liters == 165_894
    assert state.cycle_water_liters == 7
    assert state.total_water_liters == 165_901
