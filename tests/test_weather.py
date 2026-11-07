from pathlib import Path
import sys

import pytest


THU_MUC_GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(THU_MUC_GOC / "src"))

from weather import KhoDuLieuThoiTiet


THU_MUC_DA_XU_LY = THU_MUC_GOC / "data" / "processed"
pytestmark = pytest.mark.skipif(
    not (THU_MUC_DA_XU_LY / "wind.nc").exists(),
    reason="Run src/normalize_data.py before weather tests.",
)


@pytest.fixture()
def kho_du_lieu():
    with KhoDuLieuThoiTiet(THU_MUC_DA_XU_LY) as kho_thoi_tiet:
        yield kho_thoi_tiet


def test_truy_van_ngoai_bien_hop_le(kho_du_lieu):
    ket_qua = kho_du_lieu.weather_at(15.0, 110.2, "2024-10-10T12:00:00Z")
    assert ket_qua["valid"] is True
    assert ket_qua["wind_u_mps"] is not None
    assert ket_qua["wind_v_mps"] is not None
    assert ket_qua["wave_hs_m"] is not None


def test_ngoai_pham_vi_khong_gian_khong_hop_le(kho_du_lieu):
    ket_qua = kho_du_lieu.weather_at(25.0, 115.0, "2024-10-12T00:00:00Z")
    assert ket_qua["valid"] is False
    assert "out_of_range" in ket_qua["note"]


def test_ngoai_pham_vi_thoi_gian_khong_hop_le(kho_du_lieu):
    ket_qua = kho_du_lieu.weather_at(15.0, 110.2, "2024-10-20T00:00:00Z")
    assert ket_qua["valid"] is False
    assert "time_out_of_range" in ket_qua["note"]


def test_o_thieu_tren_dat_khong_bi_thay_bang_khong(kho_du_lieu):
    ket_qua = kho_du_lieu.weather_at(16.0, 106.0, "2024-10-12T00:00:00Z")
    assert ket_qua["valid"] is False
    assert ket_qua["wave_hs_m"] is None
    assert ket_qua["wave_hs_m"] != 0


def test_song_sat_bo_dung_o_bien_hop_le_gan_nhat(kho_du_lieu):
    ket_qua = kho_du_lieu.weather_at(
        10.39, 106.98, "2024-10-12T00:00:00Z"
    )
    assert ket_qua["valid"] is True
    assert ket_qua["wave_hs_m"] is not None
    assert "nearest_valid_sea_cell" in ket_qua["note"]
    assert (
        ket_qua["source"]["waves"]["distance_from_query_nm"]
        <= 30.0
    )
