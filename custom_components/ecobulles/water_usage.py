"""Pure helpers for Ecobulles water usage accounting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WaterUsageState:
    """Persisted water accounting state.

    `cycle_water_liters` mirrors the Ecobulles counter for the active CO2 bottle.
    `completed_cycles_liters` stores finished bottle cycles so `total_water_liters`
    can remain monotonic even when the device counter resets.
    """

    cycle_water_liters: int = 0
    completed_cycles_liters: int = 0
    bottle_changes: int = 0

    @property
    def total_water_liters(self) -> int:
        """Return immutable lifetime water usage."""
        return self.completed_cycles_liters + self.cycle_water_liters

    def apply_cycle_value(self, new_cycle_water_liters: int) -> bool:
        """Apply a device reading and detect a CO2 bottle replacement."""
        if new_cycle_water_liters < 0:
            raise ValueError("Water usage cannot be negative")

        bottle_changed = (
            self.cycle_water_liters > 0
            and new_cycle_water_liters < self.cycle_water_liters
        )
        if bottle_changed:
            self.completed_cycles_liters += self.cycle_water_liters
            self.bottle_changes += 1

        self.cycle_water_liters = new_cycle_water_liters
        return bottle_changed

    def as_dict(self) -> dict[str, int]:
        """Serialize the state for storage."""
        return {
            "cycle_water_liters": self.cycle_water_liters,
            "completed_cycles_liters": self.completed_cycles_liters,
            "bottle_changes": self.bottle_changes,
        }

    @classmethod
    def from_dict(cls, raw: dict | None) -> "WaterUsageState":
        """Restore the state from storage."""
        raw = raw or {}
        return cls(
            cycle_water_liters=int(raw.get("cycle_water_liters", 0)),
            completed_cycles_liters=int(raw.get("completed_cycles_liters", 0)),
            bottle_changes=int(raw.get("bottle_changes", 0)),
        )
