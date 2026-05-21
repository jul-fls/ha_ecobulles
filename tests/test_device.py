"""Tests for Ecobulles device metadata helpers."""

from custom_components.ecobulles.device import model_from_serial_number


def test_model_from_serial_number() -> None:
    """Infer known model names from observed serial prefixes."""
    assert model_from_serial_number("XC240007") == "Ecobulles Expert"
    assert model_from_serial_number("E123456") == "Ecobulles Équilibre"
    assert model_from_serial_number("Z123456") == "Ecobulles"
    assert model_from_serial_number(None) == "Ecobulles"
