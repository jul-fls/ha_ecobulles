"""Generated client identifiers for Ecobulles API login."""

from __future__ import annotations

import secrets


def generate_registration_id() -> str:
    """Generate a plausible FCM-like registration id accepted by the API."""
    return f"{secrets.token_urlsafe(8)}:APA91b{secrets.token_urlsafe(120)}"


def generate_sand() -> str:
    """Generate a hex-ish sand value accepted by the API."""
    return secrets.token_hex(5).upper()
