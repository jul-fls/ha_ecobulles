"""Test the Home Assistant adapter around the standalone API library.

Protocol behavior is tested in pyecobulles, not duplicated here.
"""

from unittest.mock import patch

from custom_components.ecobulles.api import EcobullesClient


def test_adapter_passes_credentials_and_shared_session(hass) -> None:
    """Home Assistant owns the web session; pyecobulles owns portal auth."""
    with patch("custom_components.ecobulles.api.async_get_clientsession") as session:
        client = EcobullesClient(hass, email="user@example.com", password="secret")

    session.assert_called_once_with(hass)
    assert client._session is session.return_value
    assert client._email == "user@example.com"
    assert client._password == "secret"


def test_adapter_accepts_explicit_session() -> None:
    """Scripts and tests can inject a session without a Home Assistant object."""
    supplied_session = object()
    client = EcobullesClient(
        session=supplied_session, email="user@example.com", password="secret"
    )
    assert client._session is supplied_session
