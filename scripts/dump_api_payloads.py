"""Dump Ecobulles API payloads for local debugging.

The script writes a redacted JSON file and does not print your password.

Examples:
    # .env
    ECOBULLES_EMAIL=you@example.com
    ECOBULLES_PASSWORD=secret

    python scripts/dump_api_payloads.py

    python scripts/dump_api_payloads.py --eco-ref "44B7D095E9C6" --output ecobulles_dump.json
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from env_helpers import load_dotenv

BASE_URL = "https://ecobulles.agom.net/cmd/"
USER_AGENT = "Ecobulles"
REGISTRATION_ID = (
    "cI7TFH55eX4:APA91bE-DyQ1QgCIcO2BBfIL1MiAl_afxm9t4o4jQIyXazceonlcmqk"
    "UF7BHwZ4J_r06EpVxOY0n8bOIm-0a7VpjItHLBM61-fdEBj4Yy_gR5dyDbyvGtI7"
    "YbFHwqfGTwN-eg_4kyKy4"
)
SAND = "B3A2F41213"
REDACTED = "***REDACTED***"


def api_post(endpoint: str, payload: dict[str, str]) -> dict:
    """Post form data to the Ecobulles API."""
    request = Request(
        f"{BASE_URL}{endpoint}",
        data=urlencode(payload).encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def authenticate(email: str, password: str) -> dict:
    """Authenticate and return the login payload."""
    return api_post(
        "loginAppUserCo2.php",
        {
            "email": email,
            "password": hashlib.sha1(password.encode("utf-8")).hexdigest(),
            "registrationId": REGISTRATION_ID,
            "sand": SAND,
        },
    )


def redact(value):
    """Recursively redact likely private fields."""
    if isinstance(value, dict):
        redacted = {}
        for key, child in value.items():
            lowered = key.lower()
            if any(
                needle in lowered
                for needle in (
                    "email",
                    "password",
                    "token",
                    "registration",
                    "sand",
                    "userid",
                    "user_id",
                )
            ):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact(child)
        return redacted
    if isinstance(value, list):
        return [redact(child) for child in value]
    return value


def main() -> int:
    """Run the dump."""
    load_dotenv(ENV_PATH)
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.getenv("ECOBULLES_EMAIL"))
    parser.add_argument("--password", default=os.getenv("ECOBULLES_PASSWORD"))
    parser.add_argument("--eco-ref", default=os.getenv("ECOBULLES_ECO_REF"))
    parser.add_argument("--output", default="ecobulles_api_dump.redacted.json")
    args = parser.parse_args()

    login_payload = None
    eco_ref = args.eco_ref
    if not eco_ref:
        if not args.email or not args.password:
            raise SystemExit(
                "Provide --eco-ref, or provide --email/--password "
                "(or ECOBULLES_EMAIL/ECOBULLES_PASSWORD env vars)."
            )
        login_payload = authenticate(args.email, args.password)
        if int(login_payload.get("status", 0)) != 1:
            raise SystemExit("Ecobulles authentication failed.")
        eco_ref = login_payload["data"]["eco_ref"]

    now = datetime.now().replace(microsecond=0)
    start = now - timedelta(days=7)

    device_info = api_post("getAppUserCo2.php", {"eco_ref": eco_ref})
    usage = api_post(
        "getConsoBoiteItemAppFilter.php",
        {
            "eco_ref": eco_ref,
            "eau": "1",
            "startdate": start.strftime("%Y-%m-%d %H:%M:%S"),
            "stopdate": now.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )

    dump = redact(
        {
            "eco_ref": eco_ref,
            "login": login_payload,
            "device_info": device_info,
            "usage_last_7_days": usage,
        }
    )
    output = Path(args.output)
    output.write_text(json.dumps(dump, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote redacted API dump to: {output.resolve()}")
    print("Tip: search the file for model, type, gamme, expert, equilibre, équilibre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
