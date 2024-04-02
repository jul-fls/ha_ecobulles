from datetime import datetime, timedelta
from homeassistant.util.dt import now as hass_now
import aiohttp
import asyncio
import hashlib
import logging

_LOGGER = logging.getLogger(__name__)


class EcobullesClient:
    BASE_URL = "https://ecobulles.agom.net/cmd/"
    USER_AGENT = "Ecobulles"

    def hash_password(self, password):
        """Hash the password using SHA-1."""
        return hashlib.sha1(password.encode("utf-8")).hexdigest()

    async def authenticate(self, email, password):
        """Authenticate with the Ecobulles API."""
        async with aiohttp.ClientSession() as session:
            hashed_password = self.hash_password(password)
            payload = {
                "email": email,
                "password": hashed_password,
                "registrationId": "cI7TFH55eX4:APA91bE-DyQ1QgCIcO2BBfIL1MiAl_afxm9t4o4jQIyXazceonlcmqkUF7BHwZ4J_r06EpVxOY0n8bOIm-0a7VpjItHLBM61-fdEBj4Yy_gR5dyDbyvGtI7YbFHwqfGTwN-eg_4kyKy4",
                "sand": "B3A2F41213",
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": self.USER_AGENT,
            }
            async with session.post(
                f"{self.BASE_URL}loginAppUserCo2.php", data=payload, headers=headers
            ) as response:
                if response.status == 200:
                    # data = await response.json()
                    # content = await response.content.read()
                    content = await response.json(content_type=None)
                    auth_status = int(content.get("status"))
                    if auth_status == 1:
                        # Authentication successful
                        user_id = content.get("data").get("userid")
                        eco_ref = content.get("data").get("eco_ref")
                        boitier_name = (
                            content.get("data")
                            .get("conso")
                            .get("boite")
                            .get("name")
                            .strip()
                        )
                        return True, user_id, eco_ref, boitier_name
                else:
                    # Handle unsuccessful login attempts or raise an exception
                    return False, None, None, None

    async def getDeviceInfo(self, eco_ref):
        """Fetch some data from the Ecobulles API after authentication."""
        payload = {"eco_ref": eco_ref}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": self.USER_AGENT,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}getAppUserCo2.php", data=payload, headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    return data
                return None

    async def getTotalWaterAndCo2Usage(self, eco_ref, hass):
        """Fetch CO2 usage data from the Ecobulles API."""

        current_time = hass_now()
        startdate = (current_time).strftime("%Y-%m-%d %H:00:00")
        stopdate = (current_time + timedelta(hours=1)).strftime("%Y-%m-%d %H:00:00")
        payload = {
            "eco_ref": eco_ref,
            "eau": "1",
            # "co2": "1",
            "startdate": startdate,
            "stopdate": stopdate,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": self.USER_AGENT,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}getConsoBoiteItemAppFilter.php",
                data=payload,
                headers=headers,
            ) as response:
                if response.status == 200:
                    data_raw = await response.json(content_type=None)
                    infoconso = data_raw.get("data", {}).get("infoconso", {})
                    graphs = infoconso.get("graph", [])
                    last_updated = None
                    if graphs:  # Check if the graph list is not empty
                        # Assuming you're interested in the last entry's date
                        last_graph_entry = graphs[
                            -1
                        ]  # Get the last entry in the graph list
                        last_updated = (
                            last_graph_entry.get("date")
                            .replace(" ", "T")
                            .replace("/", "-")
                        )
                    total_gas = infoconso.get("total_gas")
                    total_eau = infoconso.get("total_eau")
                    data = {
                        "total_gas": int(total_gas) if total_gas is not None else 0,
                        "total_eau": int(total_eau) if total_eau is not None else 0,
                        "last_updated": last_updated,
                    }
                    return data
                return None
