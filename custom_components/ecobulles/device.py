"""Device metadata helpers for Ecobulles."""

from __future__ import annotations


def model_from_serial_number(serial_number: str | None) -> str:
    """Infer the Ecobulles model from the serial number prefix.

    The API does not currently expose an explicit product model. Based on
    observed serials, `X...` appears to identify Expert devices and `E...`
    appears to identify Équilibre devices. Unknown prefixes deliberately fall
    back to the generic brand name.
    """
    if not serial_number:
        return "Ecobulles"

    prefix = serial_number.strip().upper()[:1]
    if prefix == "X":
        return "Ecobulles Expert"
    if prefix == "E":
        return "Ecobulles Équilibre"
    return "Ecobulles"
