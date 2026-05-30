"""Home Assistant adapter for the pyecobulles API client."""

from __future__ import annotations

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.dt import now as hass_now
from pyecobulles import EcobullesClient as PyEcobullesClient


class EcobullesClient(PyEcobullesClient):
    """pyecobulles client wired to Home Assistant's shared web session."""

    def __init__(
        self, hass: HomeAssistant | None = None, session: ClientSession | None = None
    ) -> None:
        """Initialize the client with Home Assistant's aiohttp session."""
        super().__init__(
            session=session or (async_get_clientsession(hass) if hass else None),
            now_fn=hass_now,
        )
