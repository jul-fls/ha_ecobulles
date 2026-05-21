"""Analyze Ecobulles water/CO2 ratios directly from the cloud API.

The script queries precise time windows instead of relying on Home Assistant
history exports. It never prints the password.

Examples:
    $env:ECOBULLES_EMAIL="you@example.com"
    $env:ECOBULLES_PASSWORD="secret"
    python scripts/analyze_co2_api_history.py --start "2026-05-17 00:00:00" --stop "2026-05-22 00:00:00" --bucket-minutes 5

    python scripts/analyze_co2_api_history.py --eco-ref "..." --start "2026-05-17 00:00:00" --days 2
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://ecobulles.agom.net/cmd/"
USER_AGENT = "Ecobulles"
REGISTRATION_ID = (
    "cI7TFH55eX4:APA91bE-DyQ1QgCIcO2BBfIL1MiAl_afxm9t4o4jQIyXazceonlcmqk"
    "UF7BHwZ4J_r06EpVxOY0n8bOIm-0a7VpjItHLBM61-fdEBj4Yy_gR5dyDbyvGtI7"
    "YbFHwqfGTwN-eg_4kyKy4"
)
SAND = "B3A2F41213"


@dataclass(frozen=True)
class WindowUsage:
    """Usage returned by the API for a time window."""

    start: datetime
    stop: datetime
    water_liters: int
    raw_co2: int
    graph_points: int = 0
    api_total_water: int = 0
    api_total_co2: int = 0
    sample_time: datetime | None = None

    @property
    def ratio(self) -> float | None:
        """Return raw CO2 units per liter."""
        if self.water_liters <= 0:
            return None
        return self.raw_co2 / self.water_liters


def parse_local_datetime(value: str) -> datetime:
    """Parse a CLI datetime."""
    return datetime.fromisoformat(value.replace("T", " "))


def api_post(endpoint: str, payload: dict[str, str]) -> dict:
    """Post form data to the Ecobulles API."""
    data = urlencode(payload).encode()
    request = Request(
        f"{BASE_URL}{endpoint}",
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def authenticate(email: str, password: str) -> str:
    """Authenticate and return eco_ref."""
    content = api_post(
        "loginAppUserCo2.php",
        {
            "email": email,
            "password": hashlib.sha1(password.encode("utf-8")).hexdigest(),
            "registrationId": REGISTRATION_ID,
            "sand": SAND,
        },
    )
    if int(content.get("status", 0)) != 1:
        raise SystemExit("Ecobulles authentication failed.")
    return content["data"]["eco_ref"]


def fetch_usage(eco_ref: str, start: datetime, stop: datetime) -> WindowUsage:
    """Fetch usage totals for one API window."""
    content = api_post(
        "getConsoBoiteItemAppFilter.php",
        {
            "eco_ref": eco_ref,
            "eau": "1",
            "startdate": start.strftime("%Y-%m-%d %H:%M:%S"),
            "stopdate": stop.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    infoconso = content.get("data", {}).get("infoconso", {})
    api_total_water = int(float(infoconso.get("total_eau") or 0))
    api_total_co2 = int(float(infoconso.get("total_gas") or 0))
    graph = infoconso.get("graph") or []
    graph_water = 0
    graph_co2 = 0
    sample_time = stop
    for point in graph:
        graph_water += int(float(point.get("water") or point.get("eau") or point.get("total_eau") or 0))
        graph_co2 += int(float(point.get("gas") or point.get("gaz") or point.get("co2") or point.get("total_gas") or 0))
        if point.get("date"):
            sample_time = datetime.strptime(point["date"], "%Y/%m/%d %H:%M:%S")

    # For broad historical windows, the API's `infoconso.total_*` values can be
    # cumulative/aggregated in a way that is not safe to sum across buckets.
    # Prefer graph points when present because they are the actual filtered
    # period samples.
    water_liters = graph_water if graph else api_total_water
    raw_co2 = graph_co2 if graph else api_total_co2

    return WindowUsage(
        start=start,
        stop=stop,
        water_liters=water_liters,
        raw_co2=raw_co2,
        graph_points=len(graph),
        api_total_water=api_total_water,
        api_total_co2=api_total_co2,
        sample_time=sample_time,
    )


def iter_windows(start: datetime, stop: datetime, bucket: timedelta):
    """Yield adjacent time windows."""
    current = start
    while current < stop:
        next_stop = min(current + bucket, stop)
        yield current, next_stop
        current = next_stop


def print_analysis(windows: list[WindowUsage]) -> None:
    """Print ratio analysis."""
    cumulative_samples = []
    seen = set()
    for window in windows:
        if not window.api_total_water and not window.api_total_co2:
            continue
        key = (window.api_total_water, window.api_total_co2)
        if key in seen:
            continue
        seen.add(key)
        cumulative_samples.append(window)

    cumulative_windows: list[WindowUsage] = []
    for previous, current in zip(cumulative_samples, cumulative_samples[1:]):
        water_delta = current.api_total_water - previous.api_total_water
        co2_delta = current.api_total_co2 - previous.api_total_co2
        if water_delta < 0 or co2_delta < 0:
            continue
        cumulative_windows.append(
            WindowUsage(
                start=previous.sample_time or previous.stop,
                stop=current.sample_time or current.stop,
                water_liters=water_delta,
                raw_co2=co2_delta,
                api_total_water=current.api_total_water,
                api_total_co2=current.api_total_co2,
                sample_time=current.sample_time,
            )
        )

    usable = [window for window in cumulative_windows if window.water_liters > 0]
    print(f"Windows queried: {len(windows)}")
    print(f"Distinct cumulative samples: {len(cumulative_samples)}")
    print(f"Windows with water usage: {len(usable)}")

    one_liter = [window for window in usable if window.water_liters == 1]
    print(f"One-liter windows found: {len(one_liter)}")
    if one_liter:
        print("\nRaw CO2 totals for exactly 1 L API windows:")
        for raw_co2, count in Counter(window.raw_co2 for window in one_liter).most_common():
            print(f"  {raw_co2}: {count} window(s)")
        print("\nDetailed 1 L windows:")
        for window in one_liter:
            verdict = "MATCH" if window.raw_co2 == 1500 else "DIFF"
            print(
                f"  {window.start} -> {window.stop}: "
                f"water 1 L, raw CO2 {window.raw_co2} ({verdict})"
            )

    ratio_counts = Counter(round(window.ratio or 0) for window in usable)
    print("\nMost common rounded raw CO2 units per liter:")
    for ratio, count in ratio_counts.most_common(15):
        print(f"  {ratio}: {count} window(s)")

    by_day: dict[str, list[WindowUsage]] = defaultdict(list)
    for window in usable:
        by_day[window.start.date().isoformat()].append(window)

    print("\nDaily rollup:")
    for day, day_windows in sorted(by_day.items()):
        water = sum(window.water_liters for window in day_windows)
        raw_co2 = sum(window.raw_co2 for window in day_windows)
        if water:
            print(
                f"  {day}: water +{water:g} L, "
                f"raw CO2 +{raw_co2:g}, ratio {raw_co2 / water:.1f} raw/L"
            )

    total_water = sum(window.water_liters for window in usable)
    total_co2 = sum(window.raw_co2 for window in usable)
    if total_water:
        print("\nWhole range:")
        print(
            f"  water +{total_water:g} L, raw CO2 +{total_co2:g}, "
            f"ratio {total_co2 / total_water:.1f} raw/L"
        )


def main() -> int:
    """Run the analysis."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.getenv("ECOBULLES_EMAIL"))
    parser.add_argument("--password", default=os.getenv("ECOBULLES_PASSWORD"))
    parser.add_argument("--eco-ref", default=os.getenv("ECOBULLES_ECO_REF"))
    parser.add_argument("--start", required=True, help="Local start datetime")
    parser.add_argument("--stop", help="Local stop datetime")
    parser.add_argument("--days", type=int, default=1, help="Used when --stop is omitted")
    parser.add_argument("--bucket-minutes", type=int, default=5)
    parser.add_argument("--debug-first-active", action="store_true")
    args = parser.parse_args()

    start = parse_local_datetime(args.start)
    stop = parse_local_datetime(args.stop) if args.stop else start + timedelta(days=args.days)
    bucket = timedelta(minutes=args.bucket_minutes)

    eco_ref = args.eco_ref
    if not eco_ref:
        if not args.email or not args.password:
            raise SystemExit(
                "Provide --eco-ref, or provide --email/--password "
                "(or ECOBULLES_EMAIL/ECOBULLES_PASSWORD env vars)."
            )
        eco_ref = authenticate(args.email, args.password)

    windows = [
        fetch_usage(eco_ref, window_start, window_stop)
        for window_start, window_stop in iter_windows(start, stop, bucket)
    ]
    if args.debug_first_active:
        for window in windows:
            if (
                window.water_liters
                or window.raw_co2
                or window.api_total_water
                or window.api_total_co2
                or window.graph_points
            ):
                raw = api_post(
                    "getConsoBoiteItemAppFilter.php",
                    {
                        "eco_ref": eco_ref,
                        "eau": "1",
                        "startdate": window.start.strftime("%Y-%m-%d %H:%M:%S"),
                        "stopdate": window.stop.strftime("%Y-%m-%d %H:%M:%S"),
                    },
                )
                print(
                    f"Debug window: {window.start} -> {window.stop}\n"
                    f"Parsed water={window.water_liters}, raw_co2={window.raw_co2}, "
                    f"api_total_water={window.api_total_water}, "
                    f"api_total_co2={window.api_total_co2}, "
                    f"graph_points={window.graph_points}"
                )
                print(json.dumps(raw.get("data", {}).get("infoconso", {}), indent=2)[:8000])
                break
    print_analysis(windows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
