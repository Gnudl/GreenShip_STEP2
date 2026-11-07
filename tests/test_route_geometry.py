"""Kiểm thử tuyến thủ công, khoảng cách WGS84, chia điểm và phát hiện đất."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


THU_MUC_GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(THU_MUC_GOC / "src"))

from route_geometry import (
    TEP_TUYEN_MAC_DINH,
    tao_bao_cao,
    tinh_khoang_cach_trac_dia_nm,
    doc_cac_tuyen,
    tinh_khoang_cach_tuyen_nm,
    chia_diem_tren_tuyen,
    chia_diem_tren_doan,
)


@pytest.fixture(scope="module")
def cac_tuyen():
    return doc_cac_tuyen(TEP_TUYEN_MAC_DINH)


@pytest.fixture(scope="module")
def bao_cao_hinh_hoc():
    # Chỉ nạp Natural Earth một lần vì kiểm tra toàn bộ đoạn cần nhiều thời gian.
    return tao_bao_cao()


def test_co_dung_ba_tuyen_thu_cong(cac_tuyen):
    assert [tuyen["route_id"] for tuyen in cac_tuyen] == ["R01", "R02", "R03"]


def test_moi_tuyen_co_it_nhat_hai_diem(cac_tuyen):
    assert all(len(tuyen["waypoints"]) >= 2 for tuyen in cac_tuyen)


def test_cac_tuyen_chung_diem_di_va_diem_den(cac_tuyen):
    cac_diem_di = {tuyen["waypoints"][0] for tuyen in cac_tuyen}
    cac_diem_den = {tuyen["waypoints"][-1] for tuyen in cac_tuyen}
    assert cac_diem_di == {(106.8333, 20.6667)}
    assert cac_diem_den == {(107.08, 10.42)}


def test_moi_toa_do_nam_trong_gioi_han(cac_tuyen):
    for tuyen in cac_tuyen:
        for kinh_do, vi_do in tuyen["waypoints"]:
            assert -180.0 <= kinh_do <= 180.0
            assert -90.0 <= vi_do <= 90.0


def test_mot_do_xich_dao_xap_xi_sau_muoi_hai_ly():
    khoang_cach_nm = tinh_khoang_cach_trac_dia_nm((0.0, 0.0), (1.0, 0.0))
    assert khoang_cach_nm == pytest.approx(60.1077, abs=0.001)


def test_moi_tuyen_co_khoang_cach_duong(cac_tuyen):
    assert all(tinh_khoang_cach_tuyen_nm(tuyen["waypoints"]) > 0.0 for tuyen in cac_tuyen)


def test_chia_doan_khong_vuot_nam_hai_ly(cac_tuyen):
    for tuyen in cac_tuyen:
        cac_diem_mau = chia_diem_tren_tuyen(tuyen["waypoints"], khoang_cach_toi_da_nm=5.0)
        cac_khoang_cach = [
            tinh_khoang_cach_trac_dia_nm(diem_thu_nhat, diem_thu_hai)
            for diem_thu_nhat, diem_thu_hai in zip(cac_diem_mau, cac_diem_mau[1:])
        ]
        assert max(cac_khoang_cach) <= 5.0 + 1e-9


def test_chia_diem_giu_nguyen_hai_dau_doan():
    diem_dau = (110.2, 15.0)
    diem_cuoi = (110.2, 13.5)
    cac_diem_mau = chia_diem_tren_doan(diem_dau, diem_cuoi, khoang_cach_toi_da_nm=5.0)
    assert cac_diem_mau[0] == diem_dau
    assert cac_diem_mau[-1] == diem_cuoi


def test_phan_loai_cat_dat_dung_du_kien(bao_cao_hinh_hoc):
    cac_ket_qua = {muc["route_id"]: muc for muc in bao_cao_hinh_hoc["routes"]}
    assert cac_ket_qua["R01"]["crosses_land"] is False
    assert cac_ket_qua["R02"]["crosses_land"] is True
    assert cac_ket_qua["R02"]["land_violating_segments"]
    assert cac_ket_qua["R03"]["crosses_land"] is False


def test_r03_la_tuyen_thay_the_khong_goi_la_ngan_nhat(bao_cao_hinh_hoc):
    cac_ket_qua = {muc["route_id"]: muc for muc in bao_cao_hinh_hoc["routes"]}
    assert cac_ket_qua["R03"]["distance_nm"] > cac_ket_qua["R01"]["distance_nm"]


def test_loai_kinh_do_khong_hop_le(tmp_path):
    tep_khong_hop_le = tmp_path / "invalid_routes.json"
    tep_khong_hop_le.write_text(
        json.dumps(
            {
                "routes": [
                    {
                        "route_id": "BAD",
                        "waypoints": [[181.0, 10.0], [107.0, 11.0]],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Longitude outside"):
        doc_cac_tuyen(tep_khong_hop_le)
