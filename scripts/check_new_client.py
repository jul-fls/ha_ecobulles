"""Smoke-test the local pyecobulles checkout with credentials from .env."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

from aiohttp import ClientSession

from env_helpers import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "ecobulles_api"))

from pyecobulles import EcobullesClient  # noqa: E402


async def main() -> None:
    load_dotenv(ROOT / ".env")
    email = os.environ["ECOBULLES_EMAIL"]
    password = os.environ["ECOBULLES_PASSWORD"]
    async with ClientSession() as session:
        client = EcobullesClient(session, email=email, password=password)
        success, _, eco_ref, name = await client.authenticate(email, password)
        print("Authentication:", success, "box:", name)
        if not success or eco_ref is None:
            return
        usage, device, alerts = await asyncio.gather(
            client.get_total_water_and_co2_usage(eco_ref),
            client.get_device_info(eco_ref),
            client.get_alerts(eco_ref),
        )
        print("Usage:", usage)
        box = (device or {}).get("data", {}).get("boite", {})
        print(
            "Device:",
            {
                key: box.get(key)
                for key in (
                    "name",
                    "firm_ver",
                    "num_serie",
                    "activated",
                    "locked",
                    "suspended",
                    "lastdatereceive",
                    "installdate",
                    "bottle_empty",
                )
            },
        )
        print("Alerts:", len(alerts), "active:", sum(x.get("currently") == 1 for x in alerts))


if __name__ == "__main__":
    asyncio.run(main())
