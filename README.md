# GreenShip STEP 2

Prepare real weather and land data, then build a deterministic route evaluation foundation before implementing COA/RIME.

## Project structure

- `config/`: scenario and ship assumptions.
- `data/raw/`: downloaded source data; do not modify in place.
- `data/processed/`: normalized UTC and SI-unit subsets.
- `data/land/`: Natural Earth land polygons.
- `data/routes/`: manual route definitions.
- `src/`: data inspection, normalization, weather lookup, geometry, constraints, and evaluator code.
- `tests/`: automated checks.
- `outputs/`: generated tables, JSON, maps, and logs.
- `screenshots/`: manually captured terminal or provider-interface evidence.
- `reports/`: STEP 2 report material.

## Setup

Place the downloaded files at:

```text
data/raw/era5_wind_20241010_20241014.nc
data/raw/era5_waves_20241010_20241014.nc
data/raw/cmems_currents_daily_20241010_20241014_surface.nc
data/land/ne_10m_land/ne_10m_land.shp
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the current data workflow:

```powershell
python .\src\inspect_data.py
python .\src\normalize_data.py
python .\src\check_weather.py
python .\src\map_domain.py
python -m pytest .\tests\test_weather.py -q
```

Generated figures belong in `outputs/`. The `screenshots/` directory is reserved for screenshots manually captured by the group as evidence.

Missing weather values remain missing and are never replaced with zero. Wind and waves are mandatory for a valid lookup; currents are optional. This project is a research simulation and is not suitable for navigation.
