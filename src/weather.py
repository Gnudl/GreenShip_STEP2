"""Nearest-neighbour weather lookup for normalized STEP 2 datasets."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def _utc_timestamp(value: str | pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp


def _iso_utc(value) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat().replace("+00:00", "Z")


class WeatherStore:
    """Open normalized weather files once and answer deterministic lookups."""

    def __init__(self, processed_dir: str | Path = DEFAULT_PROCESSED_DIR):
        self.processed_dir = Path(processed_dir)
        paths = {
            "wind": self.processed_dir / "wind.nc",
            "waves": self.processed_dir / "waves.nc",
            "currents": self.processed_dir / "currents.nc",
        }
        missing = [str(path) for path in paths.values() if not path.exists()]
        if missing:
            raise FileNotFoundError(
                "Normalized data missing. Run src/normalize_data.py first: " + ", ".join(missing)
            )
        self.datasets = {name: xr.open_dataset(path) for name, path in paths.items()}

    def close(self) -> None:
        for dataset in self.datasets.values():
            dataset.close()

    def __enter__(self) -> "WeatherStore":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @staticmethod
    def _lookup(
        dataset: xr.Dataset,
        variables: tuple[str, ...],
        latitude: float,
        longitude: float,
        query_time: pd.Timestamp,
    ) -> dict:
        bounds = {
            "latitude": (float(dataset.latitude.min()), float(dataset.latitude.max())),
            "longitude": (float(dataset.longitude.min()), float(dataset.longitude.max())),
            "time": (
                _utc_timestamp(dataset.time.values[0]),
                _utc_timestamp(dataset.time.values[-1]),
            ),
        }
        errors = []
        if not bounds["latitude"][0] <= latitude <= bounds["latitude"][1]:
            errors.append("latitude_out_of_range")
        if not bounds["longitude"][0] <= longitude <= bounds["longitude"][1]:
            errors.append("longitude_out_of_range")
        if not bounds["time"][0] <= query_time <= bounds["time"][1]:
            errors.append("time_out_of_range")
        if errors:
            return {"valid": False, "values": {}, "errors": errors, "matched": None}

        query_time_naive = query_time.tz_localize(None).to_datetime64()
        selected = dataset.sel(
            latitude=latitude,
            longitude=longitude,
            time=query_time_naive,
            method="nearest",
        )
        values = {}
        missing_variables = []
        for variable in variables:
            value = float(selected[variable].values)
            if np.isfinite(value):
                values[variable] = value
            else:
                values[variable] = None
                missing_variables.append(variable)

        return {
            "valid": not missing_variables,
            "values": values,
            "errors": [f"missing:{name}" for name in missing_variables],
            "matched": {
                "latitude": float(selected.latitude.values),
                "longitude": float(selected.longitude.values),
                "time_utc": _iso_utc(selected.time.values),
            },
        }

    def weather_at(self, lat: float, lon: float, time_utc: str | pd.Timestamp) -> dict:
        notes: list[str] = []
        if not -90.0 <= float(lat) <= 90.0:
            return self._invalid_result("latitude_invalid")
        if not -180.0 <= float(lon) <= 180.0:
            return self._invalid_result("longitude_invalid")
        try:
            query_time = _utc_timestamp(time_utc)
        except Exception as error:
            return self._invalid_result(f"time_invalid:{error}")

        wind = self._lookup(self.datasets["wind"], ("u10", "v10"), lat, lon, query_time)
        waves = self._lookup(self.datasets["waves"], ("swh",), lat, lon, query_time)
        currents = self._lookup(self.datasets["currents"], ("uo", "vo"), lat, lon, query_time)

        for group_name, lookup in (("wind", wind), ("waves", waves)):
            notes.extend(f"{group_name}:{error}" for error in lookup["errors"])
        if not currents["valid"]:
            notes.extend(f"currents_optional:{error}" for error in currents["errors"])

        mandatory_valid = wind["valid"] and waves["valid"]
        return {
            "wave_hs_m": waves["values"].get("swh"),
            "wind_u_mps": wind["values"].get("u10"),
            "wind_v_mps": wind["values"].get("v10"),
            "current_u_mps": currents["values"].get("uo"),
            "current_v_mps": currents["values"].get("vo"),
            "valid": mandatory_valid,
            "note": "; ".join(notes) if notes else "ok",
            "query": {"latitude": float(lat), "longitude": float(lon), "time_utc": _iso_utc(query_time)},
            "source": {
                "wind": wind["matched"],
                "waves": waves["matched"],
                "currents": currents["matched"],
            },
        }

    @staticmethod
    def _invalid_result(note: str) -> dict:
        return {
            "wave_hs_m": None,
            "wind_u_mps": None,
            "wind_v_mps": None,
            "current_u_mps": None,
            "current_v_mps": None,
            "valid": False,
            "note": note,
            "query": None,
            "source": {"wind": None, "waves": None, "currents": None},
        }


def weather_at(
    lat: float,
    lon: float,
    time_utc: str | pd.Timestamp,
    processed_dir: str | Path = DEFAULT_PROCESSED_DIR,
) -> dict:
    """Convenience interface matching the STEP 2 data contract."""
    with WeatherStore(processed_dir) as store:
        return store.weather_at(lat, lon, time_utc)

