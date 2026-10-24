"""Normalize GreenShip STEP 2 weather inputs without filling missing values."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DATASETS = {
    "wind": {
        "input": RAW_DIR / "era5_wind_20241010_20241014.nc",
        "output": PROCESSED_DIR / "wind.nc",
        "variables": ("u10", "v10"),
    },
    "waves": {
        "input": RAW_DIR / "era5_waves_20241010_20241014.nc",
        "output": PROCESSED_DIR / "waves.nc",
        "variables": ("swh",),
    },
    "currents": {
        "input": RAW_DIR / "cmems_currents_daily_20241010_20241014_surface.nc",
        "output": PROCESSED_DIR / "currents.nc",
        "variables": ("uo", "vo"),
    },
}

CANONICAL_UNITS = {
    "u10": "m s-1",
    "v10": "m s-1",
    "swh": "m",
    "uo": "m s-1",
    "vo": "m s-1",
}


def _iso_utc(value: np.datetime64) -> str:
    return f"{np.datetime_as_string(value, unit='s')}Z"


def normalize_one(name: str, specification: dict) -> dict:
    input_path: Path = specification["input"]
    output_path: Path = specification["output"]
    variables: tuple[str, ...] = specification["variables"]
    if not input_path.exists():
        raise FileNotFoundError(f"Missing raw dataset: {input_path}")

    with xr.open_dataset(input_path) as raw:
        dataset = raw.load()

    if "valid_time" in dataset.coords:
        dataset = dataset.rename({"valid_time": "time"})
    required_coordinates = {"time", "latitude", "longitude"}
    missing_coordinates = required_coordinates.difference(dataset.coords)
    if missing_coordinates:
        raise ValueError(f"{name}: missing coordinates {sorted(missing_coordinates)}")

    missing_variables = set(variables).difference(dataset.data_vars)
    if missing_variables:
        raise ValueError(f"{name}: missing variables {sorted(missing_variables)}")

    dataset = dataset[list(variables)]
    if "depth" in dataset.dims:
        surface_depth = float(dataset["depth"].values[0])
        dataset = dataset.isel(depth=0, drop=True)
        dataset.attrs["selected_surface_depth_m"] = surface_depth

    dataset = dataset.sortby("time").sortby("latitude").sortby("longitude")
    if np.any(np.diff(dataset["time"].values) < np.timedelta64(0, "ns")):
        raise ValueError(f"{name}: time is not monotonic")

    for variable in variables:
        original_unit = dataset[variable].attrs.get("units", "UNKNOWN")
        dataset[variable].attrs["original_units"] = original_unit
        dataset[variable].attrs["units"] = CANONICAL_UNITS[variable]

    dataset["time"].attrs.update({"timezone": "UTC", "standard_name": "time"})
    dataset["latitude"].attrs.setdefault("units", "degrees_north")
    dataset["longitude"].attrs.setdefault("units", "degrees_east")
    dataset.attrs.update(
        {
            "processing_level": "GreenShip STEP 2 normalized subset",
            "missing_value_policy": "Missing values retained as NaN; never filled with zero.",
            "source_file": str(input_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        }
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    encoding = {
        variable: {"zlib": True, "complevel": 4, "dtype": "float32"}
        for variable in variables
    }
    dataset.to_netcdf(output_path, engine="netcdf4", encoding=encoding)

    variable_stats = {}
    for variable in variables:
        values = np.asarray(dataset[variable].values)
        finite = np.isfinite(values)
        variable_stats[variable] = {
            "unit": dataset[variable].attrs["units"],
            "minimum": float(np.nanmin(values)) if finite.any() else None,
            "maximum": float(np.nanmax(values)) if finite.any() else None,
            "missing_percent": round(100.0 * (1.0 - finite.mean()), 6),
        }

    return {
        "dataset": name,
        "input": str(input_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "output": str(output_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "sizes": dict(dataset.sizes),
        "time_start_utc": _iso_utc(dataset["time"].values[0]),
        "time_end_utc": _iso_utc(dataset["time"].values[-1]),
        "latitude_min": float(dataset["latitude"].min()),
        "latitude_max": float(dataset["latitude"].max()),
        "longitude_min": float(dataset["longitude"].min()),
        "longitude_max": float(dataset["longitude"].max()),
        "variables": variable_stats,
    }


def main() -> None:
    reports = [normalize_one(name, specification) for name, specification in DATASETS.items()]
    report_path = PROJECT_ROOT / "outputs" / "normalization_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(reports, indent=2, ensure_ascii=False))
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()

