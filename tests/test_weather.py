from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from weather import WeatherStore


PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
pytestmark = pytest.mark.skipif(
    not (PROCESSED_DIR / "wind.nc").exists(),
    reason="Run src/normalize_data.py before weather tests.",
)


@pytest.fixture()
def store():
    with WeatherStore(PROCESSED_DIR) as weather_store:
        yield weather_store


def test_open_sea_query_is_valid(store):
    result = store.weather_at(15.0, 110.2, "2024-10-10T12:00:00Z")
    assert result["valid"] is True
    assert result["wind_u_mps"] is not None
    assert result["wind_v_mps"] is not None
    assert result["wave_hs_m"] is not None


def test_outside_spatial_domain_is_invalid(store):
    result = store.weather_at(25.0, 115.0, "2024-10-12T00:00:00Z")
    assert result["valid"] is False
    assert "out_of_range" in result["note"]


def test_outside_time_domain_is_invalid(store):
    result = store.weather_at(15.0, 110.2, "2024-10-20T00:00:00Z")
    assert result["valid"] is False
    assert "time_out_of_range" in result["note"]


def test_missing_land_cell_is_not_replaced_by_zero(store):
    result = store.weather_at(16.0, 106.0, "2024-10-12T00:00:00Z")
    assert result["valid"] is False
    assert result["wave_hs_m"] is None
    assert result["wave_hs_m"] != 0

