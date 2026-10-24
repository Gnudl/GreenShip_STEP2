"""Draw the STEP 2 data domain and check model endpoints against land polygons.

The Natural Earth shapefile is read with Python's standard library so this
evidence script does not add a GIS package dependency. Later geometric route
intersection code should use a tested geometry library.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import matplotlib.pyplot as plt
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHAPEFILE = PROJECT_ROOT / "data" / "land" / "ne_10m_land" / "ne_10m_land.shp"
SCENARIO_FILE = PROJECT_ROOT / "config" / "scenario.yaml"
MAP_DIR = PROJECT_ROOT / "outputs" / "maps"


def read_polygon_rings(path: Path) -> list[list[tuple[float, float]]]:
    """Read Polygon records from an ESRI shapefile as (longitude, latitude) rings."""
    rings: list[list[tuple[float, float]]] = []
    with path.open("rb") as stream:
        header = stream.read(100)
        if len(header) != 100 or struct.unpack(">i", header[:4])[0] != 9994:
            raise ValueError(f"Invalid shapefile header: {path}")

        while True:
            record_header = stream.read(8)
            if not record_header:
                break
            if len(record_header) != 8:
                raise ValueError("Truncated shapefile record header")
            _record_number, content_length_words = struct.unpack(">2i", record_header)
            content = stream.read(content_length_words * 2)
            if len(content) != content_length_words * 2:
                raise ValueError("Truncated shapefile record")

            shape_type = struct.unpack_from("<i", content, 0)[0]
            if shape_type == 0:
                continue
            if shape_type not in (5, 15, 25):
                raise ValueError(f"Expected polygon shapefile, found shape type {shape_type}")

            number_of_parts, number_of_points = struct.unpack_from("<2i", content, 36)
            parts = list(struct.unpack_from(f"<{number_of_parts}i", content, 44))
            point_offset = 44 + number_of_parts * 4
            points = [
                struct.unpack_from("<2d", content, point_offset + index * 16)
                for index in range(number_of_points)
            ]
            boundaries = parts + [number_of_points]
            for start, end in zip(boundaries, boundaries[1:]):
                if end - start >= 3:
                    rings.append(points[start:end])
    return rings


def point_in_ring(longitude: float, latitude: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    previous_x, previous_y = ring[-1]
    for current_x, current_y in ring:
        crosses = (current_y > latitude) != (previous_y > latitude)
        if crosses:
            intersection_x = (previous_x - current_x) * (latitude - current_y) / (previous_y - current_y) + current_x
            if longitude < intersection_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def point_on_land(longitude: float, latitude: float, rings: list[list[tuple[float, float]]]) -> bool:
    # Even-odd rule handles exterior rings and holes for this diagnostic plot.
    return sum(point_in_ring(longitude, latitude, ring) for ring in rings) % 2 == 1


def overlaps_domain(ring: list[tuple[float, float]], west: float, east: float, south: float, north: float) -> bool:
    longitudes = [point[0] for point in ring]
    latitudes = [point[1] for point in ring]
    return not (max(longitudes) < west or min(longitudes) > east or max(latitudes) < south or min(latitudes) > north)


def main() -> None:
    if not SHAPEFILE.exists():
        raise FileNotFoundError(SHAPEFILE)
    scenario = yaml.safe_load(SCENARIO_FILE.read_text(encoding="utf-8"))
    domain = scenario["data_contract"]["bounding_box"]
    west, east = float(domain["west"]), float(domain["east"])
    south, north = float(domain["south"]), float(domain["north"])
    rings = read_polygon_rings(SHAPEFILE)

    origin = scenario["main_route"]["origin"]
    destination = scenario["main_route"]["destination"]
    endpoints = {
        "origin": {
            "name": origin["name"],
            "latitude": float(origin["latitude"]),
            "longitude": float(origin["longitude"]),
        },
        "destination": {
            "name": destination["name"],
            "latitude": float(destination["latitude"]),
            "longitude": float(destination["longitude"]),
        },
    }
    for endpoint in endpoints.values():
        endpoint["natural_earth_land"] = point_on_land(endpoint["longitude"], endpoint["latitude"], rings)

    mini = scenario["debug_mini_case"]
    mini_points = [mini["start"], mini["end"]]
    mini_status = [
        {
            "latitude": float(point["latitude"]),
            "longitude": float(point["longitude"]),
            "natural_earth_land": point_on_land(float(point["longitude"]), float(point["latitude"]), rings),
        }
        for point in mini_points
    ]

    MAP_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "shapefile": str(SHAPEFILE.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "crs": "WGS84 / EPSG:4326",
        "polygon_ring_count": len(rings),
        "endpoints": endpoints,
        "mini_case": mini_status,
        "note": "Natural Earth is suitable for research screening, not operational navigation.",
    }
    check_path = PROJECT_ROOT / "outputs" / "land_port_check.json"
    check_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(8.5, 10))
    for ring in rings:
        if overlaps_domain(ring, west, east, south, north):
            x = [point[0] for point in ring]
            y = [point[1] for point in ring]
            ax.fill(x, y, facecolor="#d9c8a9", edgecolor="#6f604a", linewidth=0.45, zorder=1)

    ax.set_facecolor("#dbeef7")
    ax.plot(
        [endpoints["origin"]["longitude"], endpoints["destination"]["longitude"]],
        [endpoints["origin"]["latitude"], endpoints["destination"]["latitude"]],
        linestyle="--",
        color="#697077",
        linewidth=1.1,
        label="Endpoint chord (not an accepted route)",
        zorder=2,
    )
    ax.scatter(
        [endpoints["origin"]["longitude"], endpoints["destination"]["longitude"]],
        [endpoints["origin"]["latitude"], endpoints["destination"]["latitude"]],
        color=["#1565c0", "#c62828"],
        s=55,
        zorder=3,
        label="Model endpoints",
    )
    ax.plot(
        [point["longitude"] for point in mini_status],
        [point["latitude"] for point in mini_status],
        color="#2e7d32",
        linewidth=2.2,
        marker="o",
        label="Debug mini-case",
        zorder=3,
    )
    ax.set_xlim(west, east)
    ax.set_ylim(south, north)
    ax.set_xlabel("Longitude (degrees east)")
    ax.set_ylabel("Latitude (degrees north)")
    ax.set_title("STEP 2 data domain and Natural Earth land mask")
    ax.grid(color="white", linewidth=0.7, alpha=0.8)
    ax.legend(loc="lower right")
    fig.text(0.01, 0.01, "Research screening only — not for navigation", fontsize=9)
    map_path = MAP_DIR / "map_domain.png"
    fig.savefig(map_path, dpi=180, bbox_inches="tight")
    plt.close(fig)

    print(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote {check_path}")
    print(f"Wrote {map_path}")


if __name__ == "__main__":
    main()

