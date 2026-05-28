"""Fetch live Ecobulles usage from credentials stored in a local .env file.

Create a .env file in the repository root with:

ECOBULLES_EMAIL=you@example.com
ECOBULLES_PASSWORD=your-password

Then run:

python .\\scripts\\check_live_usage.py
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
SCRIPTS_DIR = Path(__file__).resolve().parent
AUTH_IDS_DIR = ROOT / "custom_components" / "ecobulles"
for path in (SCRIPTS_DIR, AUTH_IDS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from auth_ids import generate_registration_id, generate_sand

BASE_URL = "https://ecobulles.agom.net/cmd/"
USER_AGENT = "Ecobulles"


def load_env(path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE lines from a .env file."""
    values: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def sha1(value: str) -> str:
    """Hash the password the same way as the integration."""
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST form data to the Ecobulles API."""
    data = urlencode(payload).encode("utf-8")
    request = Request(
        f"{BASE_URL}{endpoint}",
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def require_env(values: dict[str, str], *names: str) -> str:
    """Return the first populated variable in names."""
    for name in names:
        if value := values.get(name):
            return value
    joined = " or ".join(names)
    raise RuntimeError(f"Missing {joined} in {ENV_PATH}")


def main() -> int:
    env = load_env(ENV_PATH)
    email = require_env(env, "ECOBULLES_EMAIL", "EMAIL")
    password = require_env(env, "ECOBULLES_PASSWORD", "PASSWORD")

    login = post(
        "loginAppUserCo2.php",
        {
            "email": email,
            "password": sha1(password),
            "registrationId": generate_registration_id(),
            "sand": generate_sand(),
        },
    )
    if int(login.get("status", 0)) != 1:
        print(json.dumps(login, indent=2, ensure_ascii=False))
        raise RuntimeError("Ecobulles authentication failed")

    data = login["data"]
    eco_ref = data["eco_ref"]
    box_name = data.get("conso", {}).get("boite", {}).get("name", "").strip()

    now = datetime.now()
    current_stopdate = now.strftime("%Y-%m-%d %H:%M:%S")
    rounded_hour_stopdate = now.strftime("%Y-%m-%d %H:00:00")

    usage_payload = {
        "eco_ref": eco_ref,
        "eau": "1",
        "startdate": "2000-01-01 00:00:00",
        "stopdate": current_stopdate,
    }
    usage = post("getConsoBoiteItemAppFilter.php", usage_payload)
    infoconso = usage.get("data", {}).get("infoconso", {})
    graph = infoconso.get("graph", [])

    rounded_usage = post(
        "getConsoBoiteItemAppFilter.php",
        {**usage_payload, "stopdate": rounded_hour_stopdate},
    )
    rounded_infoconso = rounded_usage.get("data", {}).get("infoconso", {})

    print(f"Box: {box_name or '(unnamed)'}")
    print(f"Eco ref: {eco_ref}")
    print(f"Current request stopdate: {current_stopdate}")
    print(f"Old rounded-hour stopdate: {rounded_hour_stopdate}")
    print()
    print("Current-minute totals")
    print(f"  total_eau: {int(infoconso.get('total_eau') or 0)} L")
    print(f"  total_gas: {int(infoconso.get('total_gas') or 0)}")
    print()
    print("Rounded-hour totals, for comparison")
    print(f"  total_eau: {int(rounded_infoconso.get('total_eau') or 0)} L")
    print(f"  total_gas: {int(rounded_infoconso.get('total_gas') or 0)}")

    if graph:
        print()
        print("Last graph entries returned by Ecobulles")
        for entry in graph[-5:]:
            print("  " + json.dumps(entry, ensure_ascii=False, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
