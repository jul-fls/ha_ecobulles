"""Persistent accounting for the resetting Ecobulles CO2 counter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CO2UsageState:
    """Keep valve-open time monotonic across technical counter resets."""

    offset_ms: int = 0
    last_raw_ms: int | None = None

    def apply(self, raw_total_ms: int | None) -> int | None:
        """Apply a raw counter reading and return its corrected total."""
        if raw_total_ms is None:
            return None

        raw_total_ms = int(raw_total_ms)
        if raw_total_ms < 0:
            raise ValueError("CO2 valve-open time cannot be negative")

        if self.last_raw_ms is not None and raw_total_ms < self.last_raw_ms:
            # A power cycle can reset total_gas. Preserve the completed segment,
            # but do not claim this proves that the CO2 bottle was replaced.
            self.offset_ms += self.last_raw_ms

        self.last_raw_ms = raw_total_ms
        return self.offset_ms + raw_total_ms

    def as_dict(self) -> dict[str, int | None]:
        """Serialize state for Home Assistant storage."""
        return {"offset_ms": self.offset_ms, "last_raw_ms": self.last_raw_ms}

    @classmethod
    def from_dict(cls, raw: dict[str, int | None] | None) -> "CO2UsageState":
        """Restore state from Home Assistant storage."""
        raw = raw or {}
        last_raw_ms = raw.get("last_raw_ms")
        return cls(
            offset_ms=max(0, int(raw.get("offset_ms", 0) or 0)),
            last_raw_ms=(None if last_raw_ms is None else max(0, int(last_raw_ms))),
        )
