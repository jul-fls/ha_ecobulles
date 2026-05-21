r"""Analyze Ecobulles raw CO2 history against water increments.

Usage:
    python scripts/analyze_co2_raw_history.py "C:\path\to\history.csv"
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import sys


def parse_datetime(value: str) -> datetime:
    """Parse Home Assistant CSV timestamps."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_numeric_series(path: Path) -> dict[str, list[tuple[datetime, float]]]:
    """Load numeric states grouped by entity id."""
    series: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            try:
                state = float(row["state"])
            except ValueError:
                continue
            series[row["entity_id"]].append((parse_datetime(row["last_changed"]), state))

    for values in series.values():
        values.sort()
    return series


def choose_entity(series: dict[str, list[tuple[datetime, float]]], needle: str) -> str:
    """Choose an entity containing a given name fragment."""
    matches = [entity_id for entity_id in series if needle in entity_id]
    if not matches:
        raise SystemExit(f"No numeric entity containing {needle!r} found.")
    if len(matches) > 1:
        print(f"Multiple {needle!r} entities found; using {matches[0]}")
    return matches[0]


def paired_points(
    water: list[tuple[datetime, float]],
    co2: list[tuple[datetime, float]],
    max_seconds_apart: int = 10,
) -> list[tuple[datetime, float, float]]:
    """Pair water and CO2 samples captured at nearly the same time."""
    pairs: list[tuple[datetime, float, float]] = []
    for water_time, water_value in water:
        co2_time, co2_value = min(
            co2, key=lambda item: abs((item[0] - water_time).total_seconds())
        )
        if abs((co2_time - water_time).total_seconds()) <= max_seconds_apart:
            pairs.append((water_time, water_value, co2_value))
    return pairs


def main() -> int:
    """Run the analysis."""
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    series = load_numeric_series(Path(sys.argv[1]))
    water_entity = choose_entity(series, "water_usage_total")
    co2_entity = choose_entity(series, "raw_co2_value")
    pairs = paired_points(series[water_entity], series[co2_entity])

    one_liter_steps: list[tuple[datetime, float]] = []
    all_positive_ratios: list[float] = []
    for previous, current in zip(pairs, pairs[1:]):
        _previous_time, previous_water, previous_co2 = previous
        current_time, current_water, current_co2 = current
        water_delta = current_water - previous_water
        co2_delta = current_co2 - previous_co2
        if water_delta > 0:
            all_positive_ratios.append(co2_delta / water_delta)
        if water_delta == 1:
            one_liter_steps.append((current_time, co2_delta))

    print(f"Water entity: {water_entity}")
    print(f"Raw CO2 entity: {co2_entity}")
    print(f"Paired samples: {len(pairs)}")
    print(f"One-liter intervals found: {len(one_liter_steps)}")

    if one_liter_steps:
        counts = Counter(co2_delta for _time, co2_delta in one_liter_steps)
        print("\nCO2 raw deltas for exactly +1 L intervals:")
        for co2_delta, count in counts.most_common():
            print(f"  +{co2_delta:g}: {count} time(s)")
        print("\nDetailed +1 L intervals:")
        for time, co2_delta in one_liter_steps:
            verdict = "MATCH" if co2_delta == 1500 else "DIFF"
            print(f"  {time.isoformat()} -> CO2 raw +{co2_delta:g} ({verdict})")

    if all_positive_ratios:
        ratio_counts = Counter(round(ratio) for ratio in all_positive_ratios)
        print("\nMost common rounded CO2 raw units per liter:")
        for ratio, count in ratio_counts.most_common(10):
            print(f"  {ratio}: {count} interval(s)")

    by_day: dict[str, list[tuple[datetime, float, float]]] = defaultdict(list)
    for point in pairs:
        by_day[point[0].date().isoformat()].append(point)

    print("\nDaily rollup:")
    for day, day_points in sorted(by_day.items()):
        if len(day_points) < 2:
            continue
        start_time, start_water, start_co2 = day_points[0]
        end_time, end_water, end_co2 = day_points[-1]
        water_delta = end_water - start_water
        co2_delta = end_co2 - start_co2
        if water_delta <= 0:
            continue
        print(
            f"  {day}: water +{water_delta:g} L, "
            f"raw CO2 +{co2_delta:g}, "
            f"ratio {co2_delta / water_delta:.1f} raw/L "
            f"({start_time.time()} -> {end_time.time()})"
        )

    if len(pairs) >= 2:
        first_time, first_water, first_co2 = pairs[0]
        last_time, last_water, last_co2 = pairs[-1]
        water_delta = last_water - first_water
        co2_delta = last_co2 - first_co2
        print("\nWhole export rollup:")
        print(
            f"  {first_time.isoformat()} -> {last_time.isoformat()}: "
            f"water +{water_delta:g} L, raw CO2 +{co2_delta:g}, "
            f"ratio {co2_delta / water_delta:.1f} raw/L"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
