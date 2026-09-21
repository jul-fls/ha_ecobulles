"""Compare the new portal and legacy counters without printing credentials."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

from env_helpers import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _request_json(url: str, body: dict | None = None, opener=None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with (opener.open(request, timeout=30) if opener else urlopen(request, timeout=30)) as response:
        return json.load(response)


def main() -> None:
    email = os.environ["ECOBULLES_EMAIL"]
    password = os.environ["ECOBULLES_PASSWORD"]
    portal = "https://portail.ecobulles.com"
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    login = _request_json(
        f"{portal}/api/login",
        {"email": email, "password": password, "rememberMe": False},
        opener,
    )
    print("Portal login:", login.get("status"))
    if login.get("status") != 1:
        return
    client_id = login["data"]["user_cli"]
    boxes = _request_json(
        f"{portal}/api/boitiers/search",
        {
            "page": 1,
            "pageSize": 100,
            "sorting": [],
            "filters": [{"id": "client", "value": str(client_id)}],
        },
        opener,
    )
    print("Portal boxes:", boxes.get("total"), "count:", len(boxes.get("data", [])))
    if not boxes.get("data"):
        return
    eco_ref = boxes["data"][0]["eco_ref"]
    usage = _request_json(
        f"{portal}/api/boitiers/{eco_ref}/consumption",
        {
            "filters": [
                {"id": "startdate", "value": "2000-01-01"},
                {"id": "enddate", "value": datetime.now().strftime("%Y-%m-%d")},
                {"id": "eau", "value": "1"},
                {"id": "co2", "value": "1"},
                {"id": "temp", "value": "0"},
            ]
        },
        opener,
    )["data"]["infoconso"]
    print("Portal totals:", {k: usage.get(k) for k in ("total_eau", "total_gas")})
    print("Portal graph points:", len(usage.get("graph") or []))
    short_usage = _request_json(
        f"{portal}/api/boitiers/{eco_ref}/consumption",
        {
            "filters": [
                {"id": "startdate", "value": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")},
                {"id": "enddate", "value": datetime.now().strftime("%Y-%m-%d")},
                {"id": "eau", "value": "1"},
                {"id": "co2", "value": "1"},
                {"id": "temp", "value": "0"},
            ]
        },
        opener,
    )["data"]["infoconso"]
    print("Portal 7-day totals:", {k: short_usage.get(k) for k in ("total_eau", "total_gas")})
    print("Portal 7-day graph points:", len(short_usage.get("graph") or []))

    legacy_data = urlencode(
        {
            "email": email,
            "password": hashlib.sha1(password.encode()).hexdigest(),
            "registrationId": f"{secrets.token_urlsafe(8)}:APA91b{secrets.token_urlsafe(120)}",
            "sand": secrets.token_hex(5).upper(),
        }
    ).encode()
    try:
        request = Request(
            "https://ecobulles.agom.net/cmd/loginAppUserCo2.php",
            data=legacy_data,
            headers={"User-Agent": "Ecobulles"},
        )
        with urlopen(request, timeout=15) as response:
            old_login = json.load(response)
        print("Legacy login:", old_login.get("status"))
        if old_login.get("status") == 1:
            request = Request(
                "https://ecobulles.agom.net/cmd/getConsoBoiteItemAppFilter.php",
                data=urlencode(
                    {
                        "eco_ref": eco_ref,
                        "eau": "1",
                        "startdate": "2000-01-01 00:00:00",
                        "stopdate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                ).encode(),
                headers={"User-Agent": "Ecobulles"},
            )
            with urlopen(request, timeout=30) as response:
                old_usage = json.load(response)["data"]["infoconso"]
            print(
                "Legacy totals:",
                {k: old_usage.get(k) for k in ("total_eau", "total_gas")},
            )
    except OSError as err:
        print("Legacy API unavailable:", type(err).__name__)


if __name__ == "__main__":
    main()
