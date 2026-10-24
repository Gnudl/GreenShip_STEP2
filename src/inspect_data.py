"""Audit the raw NetCDF inputs used by GreenShip STEP 2.

This script reads files without modifying them and writes machine-readable
metadata and quality statistics to outputs/. Missing values remain missing.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"

INPUTS = {
    "wind": RAW_DIR / "era5_wind_20241010_20241014.nc",
    "waves": RAW_DIR / "era5_waves_20241010_20241014.nc",
    "currents": RAW_DIR / "cmems_currents_daily_20241010_20241014_surface.nc",
}


def _scalar(value):
    if isinstance(value, (np.datetime64, pd.Timestamp)):
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            return f"{timestamp.isoformat()}Z"
        return timestamp.tz_convert("UTC").isoformat().replace("+00:00", "Z")
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (np.floating, float)):
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    return str(value)


def _coord_name(ds: xr.Dataset, candidates: tuple[str, ...]) -> str | None:
    return next((name for name in candidates if name in ds.coords), None)


def inspect_file(group: str, path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")

    rows: list[dict] = []
    with xr.open_dataset(path) as ds:
        time_name = _coord_name(ds, ("time", "valid_time"))
        lat_name = _coord_name(ds, ("latitude", "lat"))
        lon_name = _coord_name(ds, ("longitude", "lon"))
        depth_name = _coord_name(ds, ("depth",))

        common = {
            "group": group,
            "local_file": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "dimensions": json.dumps(dict(ds.sizes), sort_keys=True),
            "time_coordinate": time_name,
            "time_start_utc": _scalar(ds[time_name].min().values) if time_name else None,
            "time_end_utc": _scalar(ds[time_name].max().values) if time_name else None,
            "latitude_min": _scalar(ds[lat_name].min().values) if lat_name else None,
            "latitude_max": _scalar(ds[lat_name].max().values) if lat_name else None,
            "longitude_min": _scalar(ds[lon_name].min().values) if lon_name else None,
            "longitude_max": _scalar(ds[lon_name].max().values) if lon_name else None,
            "depth_m": _scalar(ds[depth_name].values[0]) if depth_name else None,
        }

        for variable, data in ds.data_vars.items():
            values = np.asarray(data.values)
            finite = np.isfinite(values)
            valid_count = int(finite.sum())
            total_count = int(values.size)
            missing_count = total_count - valid_count
            row = {
                **common,
                "variable": variable,
                "units_original": data.attrs.get("units", "UNKNOWN"),
                "variable_dimensions": json.dumps(list(data.dims)),
                "shape": "x".join(str(size) for size in data.shape),
                "total_cells": total_count,
                "valid_cells": valid_count,
                "missing_cells": missing_count,
                "missing_percent": round(100.0 * missing_count / total_count, 6),
                "minimum": float(np.nanmin(values)) if valid_count else None,
                "maximum": float(np.nanmax(values)) if valid_count else None,
            }
            rows.append(row)
    return rows


def write_audit_figure(frame: pd.DataFrame) -> Path:
    """Save a compact visual record for the STEP 2 evidence folder."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    figure_path = SCREENSHOT_DIR / "2_1_data_audit.png"
    display = frame[
        [
            "group",
            "variable",
            "units_original",
            "minimum",
            "maximum",
            "missing_percent",
            "time_start_utc",
            "time_end_utc",
        ]
    ].copy()
    display["minimum"] = display["minimum"].map(lambda value: f"{value:.4f}")
    display["maximum"] = display["maximum"].map(lambda value: f"{value:.4f}")
    display["missing_percent"] = display["missing_percent"].map(lambda value: f"{value:.2f}%")
    display.columns = ["Group", "Variable", "Unit", "Min", "Max", "Missing", "Start UTC", "End UTC"]

    fig, ax = plt.subplots(figsize=(16, 4.2))
    ax.axis("off")
    ax.set_title("GreenShip STEP 2 - Raw data audit", fontsize=16, fontweight="bold", pad=18)
    table = ax.table(
        cellText=display.values,
        colLabels=display.columns,
        cellLoc="center",
        loc="center",
        colWidths=[0.08, 0.07, 0.08, 0.07, 0.07, 0.08, 0.22, 0.22],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)
    for (row, _column), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor("#1f4e78")
            cell.set_text_props(color="white", fontweight="bold")
        elif row % 2 == 0:
            cell.set_facecolor("#eaf2f8")
    fig.text(
        0.01,
        0.03,
        "Missing ocean variables mainly represent land cells; values are not filled with zero.",
        fontsize=9,
    )
    fig.savefig(figure_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return figure_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for group, path in INPUTS.items():
        rows.extend(inspect_file(group, path))

    frame = pd.DataFrame(rows)
    csv_path = OUTPUT_DIR / "data_audit.csv"
    json_path = OUTPUT_DIR / "data_audit.json"
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    figure_path = write_audit_figure(frame)

    columns = [
        "group",
        "variable",
        "units_original",
        "minimum",
        "maximum",
        "missing_percent",
        "time_start_utc",
        "time_end_utc",
    ]
    print(frame[columns].to_string(index=False))
    print(f"\nWrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {figure_path}")


if __name__ == "__main__":
    main()

