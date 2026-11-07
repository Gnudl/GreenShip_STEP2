"""Kiểm thử evaluator, phép đổi đơn vị và tính ổn định của STEP 2."""

from pathlib import Path
import sys

import pytest


THU_MUC_GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(THU_MUC_GOC / "src"))

from evaluator import evaluate_route, tinh_co2_tan, tinh_nhien_lieu_tan


class MatNaDatGia:
    """Mặt nạ đất giả, cho phép điều khiển kết quả trong unit test."""

    def __init__(self, cat_dat=False):
        self.cat_dat = cat_dat

    def doan_cat_dat(self, diem_dau, diem_cuoi):
        return self.cat_dat


def tao_tau(toc_do_kn=10.0, cong_suat_kw=1000.0, sfoc=200.0, cf=3.114):
    return {
        "parameters": {
            "speed_through_water_kn": {"value": toc_do_kn, "unit": "kn"},
            "service_power_kw": {"value": cong_suat_kw, "unit": "kW"},
            "sfoc_g_per_kwh": {"value": sfoc, "unit": "g/kWh"},
            "fuel_type": {"value": "HFO"},
            "co2_emission_factor_t_per_t_fuel": {
                "value": cf,
                "unit": "tCO2/t-fuel",
            },
        }
    }


def tao_cau_hinh():
    return {
        "route_sampling": {"maximum_spacing_nm": 5.0},
        "reference_distance_nm": 100.0,
        "constraints": {
            "near_zero_segment_nm": 0.01,
            "wave": {"classification": "soft", "swh_threshold_m": 2.0},
            "detour": {
                "classification": "soft",
                "reference_route_id": "R01",
                "ratio_threshold": 1.05,
                "penalty_weight": 1.0,
            },
        },
    }


def tao_tuyen():
    return {
        "route_id": "T01",
        "name": "Tuyến kiểm thử ngoài biển",
        "waypoints": [(110.0, 15.0), (110.0, 14.0)],
    }


def thoi_tiet_hop_le(vi_do, kinh_do, thoi_gian_utc):
    return {
        "wave_hs_m": 1.0,
        "wind_u_mps": 2.0,
        "wind_v_mps": 1.0,
        "current_u_mps": None,
        "current_v_mps": None,
        "valid": True,
        "note": "ok",
        "query": {
            "latitude": vi_do,
            "longitude": kinh_do,
            "time_utc": str(thoi_gian_utc),
        },
        "source": {},
    }


def test_vi_du_tinh_tay_100_nm():
    """100 nm/10 kn=10 h; fuel=2 t; CO2=6.228 t."""
    thoi_gian_h = 100.0 / 10.0
    nhien_lieu_tan = tinh_nhien_lieu_tan(1000.0, 200.0, thoi_gian_h)
    co2_tan = tinh_co2_tan(nhien_lieu_tan, 3.114)
    assert thoi_gian_h == pytest.approx(10.0)
    assert nhien_lieu_tan == pytest.approx(2.0)
    assert co2_tan == pytest.approx(6.228)


def test_tuyen_hop_le_co_ket_qua_duong():
    ket_qua = evaluate_route(
        tao_tuyen(),
        "2024-10-10T00:00:00Z",
        tao_tau(),
        thoi_tiet_hop_le,
        MatNaDatGia(),
        tao_cau_hinh(),
    )
    assert ket_qua["feasible"] is True
    assert ket_qua["distance_nm"] > 0.0
    assert ket_qua["duration_h"] > 0.0
    assert ket_qua["fuel_t"] > 0.0
    assert ket_qua["co2_t"] > 0.0
    assert ket_qua["fitness"] == ket_qua["fuel_t"]
    assert len(ket_qua["segments"]) == 1


def test_cung_dau_vao_cho_cung_ket_qua():
    tham_so = (
        tao_tuyen(),
        "2024-10-10T00:00:00Z",
        tao_tau(),
        thoi_tiet_hop_le,
        MatNaDatGia(),
        tao_cau_hinh(),
    )
    assert evaluate_route(*tham_so) == evaluate_route(*tham_so)


def test_tuyen_cat_dat_khong_kha_thi():
    ket_qua = evaluate_route(
        tao_tuyen(),
        "2024-10-10T00:00:00Z",
        tao_tau(),
        thoi_tiet_hop_le,
        MatNaDatGia(cat_dat=True),
        tao_cau_hinh(),
    )
    assert ket_qua["feasible"] is False
    assert ket_qua["fitness"] is None
    assert any(
        muc["code"] == "LAND_CROSSING"
        for muc in ket_qua["violations"]["hard"]
    )


def test_thoi_tiet_bat_buoc_thieu_khong_kha_thi():
    def thoi_tiet_thieu(vi_do, kinh_do, thoi_gian_utc):
        mau = thoi_tiet_hop_le(vi_do, kinh_do, thoi_gian_utc)
        mau.update({"valid": False, "wave_hs_m": None, "note": "missing:swh"})
        return mau

    ket_qua = evaluate_route(
        tao_tuyen(),
        "2024-10-10T00:00:00Z",
        tao_tau(),
        thoi_tiet_thieu,
        MatNaDatGia(),
        tao_cau_hinh(),
    )
    assert ket_qua["feasible"] is False
    assert ket_qua["fitness"] is None
    assert any(
        muc["code"] == "MANDATORY_WEATHER_INVALID"
        for muc in ket_qua["violations"]["hard"]
    )


def test_dong_chay_thuan_lam_giam_thoi_gian():
    def dong_chay_thuan(vi_do, kinh_do, thoi_gian_utc):
        mau = thoi_tiet_hop_le(vi_do, kinh_do, thoi_gian_utc)
        # Tuyến đi về nam nên vo âm là dòng chảy thuận.
        mau.update({"current_u_mps": 0.0, "current_v_mps": -1.0})
        return mau

    tham_so_chung = (
        tao_tuyen(),
        "2024-10-10T00:00:00Z",
        tao_tau(),
    )
    khong_dong_chay = evaluate_route(
        *tham_so_chung, thoi_tiet_hop_le, MatNaDatGia(), tao_cau_hinh()
    )
    co_dong_chay = evaluate_route(
        *tham_so_chung, dong_chay_thuan, MatNaDatGia(), tao_cau_hinh()
    )
    assert co_dong_chay["duration_h"] < khong_dong_chay["duration_h"]
    assert co_dong_chay["fuel_t"] < khong_dong_chay["fuel_t"]


def test_sai_don_vi_tau_bi_tu_choi():
    tau = tao_tau()
    tau["parameters"]["speed_through_water_kn"]["unit"] = "m/s"
    ket_qua = evaluate_route(
        tao_tuyen(),
        "2024-10-10T00:00:00Z",
        tau,
        thoi_tiet_hop_le,
        MatNaDatGia(),
        tao_cau_hinh(),
    )
    assert ket_qua["feasible"] is False
    assert ket_qua["distance_nm"] is None
    assert ket_qua["violations"]["hard"][0]["code"] == "INPUT_INVALID"


def test_sfoc_khong_duong_bi_tu_choi():
    ket_qua = evaluate_route(
        tao_tuyen(),
        "2024-10-10T00:00:00Z",
        tao_tau(sfoc=0.0),
        thoi_tiet_hop_le,
        MatNaDatGia(),
        tao_cau_hinh(),
    )
    assert ket_qua["feasible"] is False
    assert ket_qua["fuel_t"] is None


def test_co2_tang_cung_ty_le_voi_nhien_lieu():
    assert tinh_co2_tan(4.0, 3.114) == pytest.approx(
        2.0 * tinh_co2_tan(2.0, 3.114)
    )
