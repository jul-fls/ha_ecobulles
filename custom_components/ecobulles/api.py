"""API client for the Ecobulles cloud service."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from aiohttp import ClientError
from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.dt import now as hass_now

from .auth_ids import generate_registration_id, generate_sand

_LOGGER = logging.getLogger(__name__)


class EcobullesClient:
    """Small async client for the Ecobulles mobile API."""

    BASE_URL = "https://ecobulles.agom.net/cmd/"
    USER_AGENT = "Ecobulles"

    def __init__(
        self, hass: HomeAssistant | None = None, session: ClientSession | None = None
    ) -> None:
        """Initialize the client."""
        self._session = session or (
            async_get_clientsession(hass) if hass is not None else None
        )
        self._registration_id = generate_registration_id()
        self._sand = generate_sand()

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash the password using SHA-1 as expected by the legacy API."""
        return hashlib.sha1(password.encode("utf-8")).hexdigest()

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Post form data and decode a JSON response."""
        if self._session is None:
            raise RuntimeError("EcobullesClient requires a Home Assistant session")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": self.USER_AGENT,
        }
        try:
            async with self._session.post(
                f"{self.BASE_URL}{endpoint}", data=payload, headers=headers
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    _LOGGER.warning(
                        "Ecobulles request failed for %s: HTTP %s; body=%s",
                        endpoint,
                        response.status,
                        body[:500],
                    )
                    return None
                return await response.json(content_type=None)
        except TimeoutError as err:
            raise TimeoutError(f"Ecobulles request timed out for {endpoint}") from err
        except ClientError as err:
            raise RuntimeError(f"Ecobulles request failed for {endpoint}: {err}") from err

    async def authenticate(
        self, email: str, password: str
    ) -> tuple[bool, str | None, str | None, str | None]:
        """Authenticate with the Ecobulles API."""
        content = await self.get_login_payload(email, password)
        if content is None or int(content.get("status", 0)) != 1:
            return False, None, None, None

        data = content["data"]
        return (
            True,
            data.get("userid"),
            data.get("eco_ref"),
            data.get("conso", {}).get("boite", {}).get("name", "").strip(),
        )

    async def get_login_payload(self, email: str, password: str) -> dict[str, Any] | None:
        """Authenticate and return the full login payload."""
        return await self._post(
            "loginAppUserCo2.php",
            {
                "email": email,
                "password": self.hash_password(password),
                "registrationId": self._registration_id,
                "sand": self._sand,
            },
        )

    async def get_device_info(self, eco_ref: str) -> dict[str, Any] | None:
        """Fetch device metadata."""
        return await self._post("getAppUserCo2.php", {"eco_ref": eco_ref})

    async def get_total_water_and_co2_usage(self, eco_ref: str) -> dict[str, Any] | None:
        """Fetch cumulative usage data exposed by the Ecobulles API."""
        current_time = hass_now()
        data_raw = await self._post(
            "getConsoBoiteItemAppFilter.php",
            {
                "eco_ref": eco_ref,
                "eau": "1",
                "startdate": "2000-01-01 00:00:00",
                "stopdate": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        if data_raw is None:
            return None

        infoconso = data_raw.get("data", {}).get("infoconso", {})
        graphs = infoconso.get("graph", [])
        last_updated = None
        if graphs:
            last_graph_entry = graphs[-1]
            raw_date = last_graph_entry.get("date")
            if raw_date:
                last_updated = raw_date.replace(" ", "T").replace("/", "-")

        return {
            "total_gas": int(infoconso.get("total_gas") or 0),
            "total_eau": int(infoconso.get("total_eau") or 0),
            "last_updated": last_updated,
        }
