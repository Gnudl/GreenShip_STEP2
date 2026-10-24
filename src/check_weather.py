"""Run reproducible STEP 2 weather lookup checks and save their output."""

from __future__ import annotations

import json
from pathlib import Path

from weather import WeatherStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]

QUERIES = [
    {"id": "Q01", "lat": 15.0, "lon": 110.2, "time_utc": "2024-10-10T12:00:00Z"},
    {"id": "Q02", "lat": 13.5, "lon": 110.2, "time_utc": "2024-10-12T06:00:00Z"},
    {"id": "Q03", "lat": 18.5, "lon": 108.5, "time_utc": "2024-10-14T00:00:00Z"},
    {"id": "Q04_OUTSIDE_SPACE", "lat": 25.0, "lon": 115.0, "time_utc": "2024-10-12T00:00:00Z"},
    {"id": "Q05_OUTSIDE_TIME", "lat": 15.0, "lon": 110.2, "time_utc": "2024-10-20T00:00:00Z"},
]


def main() -> None:
    results = []
    with WeatherStore() as store:
        for query in QUERIES:
            result = store.weather_at(query["lat"], query["lon"], query["time_utc"])
            results.append({"id": query["id"], **result})

    output_path = PROJECT_ROOT / "outputs" / "weather_queries.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

