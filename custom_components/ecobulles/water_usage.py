"""Pure helpers for Ecobulles water usage accounting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WaterUsageState:
    """Persist water accounting without assuming resets mean bottle changes."""

    cycle_water_liters: int = 0
    completed_cycles_liters: int = 0

    @property
    def total_water_liters(self) -> int:
        """Return immutable lifetime water usage."""
        return self.completed_cycles_liters + self.cycle_water_liters

    def apply_cycle_value(self, new_cycle_water_liters: int) -> bool:
        """Apply a reading and preserve the total across technical resets.

        The boolean return value means that the counter reset; it does not imply
        or claim that a CO2 bottle was replaced.
        """
        if new_cycle_water_liters < 0:
            raise ValueError("Water usage cannot be negative")

        counter_reset = (
            self.cycle_water_liters > 0
            and new_cycle_water_liters < self.cycle_water_liters
        )
        if counter_reset:
            self.completed_cycles_liters += self.cycle_water_liters

        self.cycle_water_liters = new_cycle_water_liters
        return counter_reset

    def as_dict(self) -> dict[str, int]:
        """Serialize the state for storage."""
        return {
            "cycle_water_liters": self.cycle_water_liters,
            "completed_cycles_liters": self.completed_cycles_liters,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, int] | None) -> "WaterUsageState":
        """Restore the state from storage."""
        raw = raw or {}
        return cls(
            cycle_water_liters=int(raw.get("cycle_water_liters", 0)),
            completed_cycles_liters=int(raw.get("completed_cycles_liters", 0)),
        )
