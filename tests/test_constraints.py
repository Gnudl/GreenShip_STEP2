"""Kiểm thử phân loại hard/soft constraints và nội dung violations."""

from pathlib import Path
import sys

import pytest


THU_MUC_GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(THU_MUC_GOC / "src"))

from constraints import kiem_tra_rang_buoc


@pytest.fixture()
def cau_hinh_rang_buoc():
    return {
        "near_zero_segment_nm": 0.01,
        "wave": {
            "classification": "soft",
            "swh_threshold_m": 2.0,
        },
        "detour": {
            "classification": "soft",
            "reference_route_id": "R01",
            "ratio_threshold": 1.05,
            "penalty_weight": 1.0,
        },
    }


def tao_hinh_hoc(khoang_cach_nm=100.0, cat_dat=False):
    return {
        "distance_nm": khoang_cach_nm,
        "spacing_valid": True,
        "maximum_sample_gap_nm": 4.9,
        "spacing_limit_nm": 5.0,
        "crosses_land": cat_dat,
        "land_violating_segments": [1] if cat_dat else [],
    }


def test_tuyen_hop_le_khong_co_vi_pham_cung(cau_hinh_rang_buoc):
    ket_qua = kiem_tra_rang_buoc(
        tao_hinh_hoc(),
        [(110.0, 15.0), (110.0, 14.0)],
        cau_hinh_rang_buoc,
        khoang_cach_tham_chieu_nm=100.0,
    )
    assert ket_qua["feasible"] is True
    assert ket_qua["violations"]["hard"] == []


def test_cat_dat_la_vi_pham_cung(cau_hinh_rang_buoc):
    ket_qua = kiem_tra_rang_buoc(
        tao_hinh_hoc(cat_dat=True),
        [(110.0, 15.0), (110.0, 14.0)],
        cau_hinh_rang_buoc,
        khoang_cach_tham_chieu_nm=100.0,
    )
    assert ket_qua["feasible"] is False
    assert ket_qua["violations"]["hard"][0]["code"] == "LAND_CROSSING"


def test_duong_vong_la_vi_pham_mem(cau_hinh_rang_buoc):
    ket_qua = kiem_tra_rang_buoc(
        tao_hinh_hoc(khoang_cach_nm=106.0),
        [(110.0, 15.0), (110.0, 14.0)],
        cau_hinh_rang_buoc,
        khoang_cach_tham_chieu_nm=100.0,
    )
    assert ket_qua["feasible"] is True
    assert ket_qua["violations"]["soft"][0]["code"] == "EXCESSIVE_DETOUR"


def test_du_lieu_thoi_tiet_thieu_la_vi_pham_cung(cau_hinh_rang_buoc):
    mau_loi = {
        "valid": False,
        "note": "waves:missing:swh",
        "query": {"latitude": 15.0, "longitude": 110.0},
    }
    ket_qua = kiem_tra_rang_buoc(
        tao_hinh_hoc(),
        [(110.0, 15.0), (110.0, 14.0)],
        cau_hinh_rang_buoc,
        khoang_cach_tham_chieu_nm=100.0,
        cac_mau_thoi_tiet=[mau_loi],
    )
    assert ket_qua["feasible"] is False
    assert (
        ket_qua["violations"]["hard"][0]["code"]
        == "MANDATORY_WEATHER_INVALID"
    )


def test_song_vuot_nguong_la_vi_pham_mem(cau_hinh_rang_buoc):
    mau_song_lon = {
        "valid": True,
        "wave_hs_m": 2.5,
        "query": {"latitude": 15.0, "longitude": 110.0},
    }
    ket_qua = kiem_tra_rang_buoc(
        tao_hinh_hoc(),
        [(110.0, 15.0), (110.0, 14.0)],
        cau_hinh_rang_buoc,
        khoang_cach_tham_chieu_nm=100.0,
        cac_mau_thoi_tiet=[mau_song_lon],
    )
    assert ket_qua["feasible"] is True
    assert ket_qua["violations"]["soft"][0]["code"] == "WAVE_HEIGHT_EXCEEDED"
    assert ket_qua["violations"]["soft"][0]["details"]["exceedance_m"] == 0.5


def test_waypoint_lap_la_vi_pham_cung(cau_hinh_rang_buoc):
    ket_qua = kiem_tra_rang_buoc(
        tao_hinh_hoc(),
        [(110.0, 15.0), (110.0, 15.0), (110.0, 14.0)],
        cau_hinh_rang_buoc,
        khoang_cach_tham_chieu_nm=100.0,
    )
    assert ket_qua["feasible"] is False
    assert ket_qua["violations"]["hard"][0]["code"] == "NEAR_ZERO_SEGMENT"
