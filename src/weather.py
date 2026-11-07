"""Tra cứu thời tiết theo điểm gần nhất từ dữ liệu STEP 2 đã chuẩn hóa."""

from __future__ import annotations

from pathlib import Path
import math

import numpy as np
import pandas as pd
import xarray as xr


THU_MUC_GOC = Path(__file__).resolve().parents[1]
THU_MUC_XU_LY_MAC_DINH = THU_MUC_GOC / "data" / "processed"
KHOANG_CACH_TIM_O_SONG_HOP_LE_TOI_DA_NM = 30.0


def tinh_khoang_cach_cau_nm(vi_do_1, kinh_do_1, vi_do_2, kinh_do_2):
    """Tính khoảng cách cung lớn gần đúng theo hải lý để chọn ô lưới."""
    ban_kinh_trai_dat_nm = 3440.065
    vi_do_1, kinh_do_1, vi_do_2, kinh_do_2 = map(
        math.radians, (vi_do_1, kinh_do_1, vi_do_2, kinh_do_2)
    )
    chenh_vi_do = vi_do_2 - vi_do_1
    chenh_kinh_do = kinh_do_2 - kinh_do_1
    gia_tri_a = (
        math.sin(chenh_vi_do / 2.0) ** 2
        + math.cos(vi_do_1)
        * math.cos(vi_do_2)
        * math.sin(chenh_kinh_do / 2.0) ** 2
    )
    return 2.0 * ban_kinh_trai_dat_nm * math.asin(math.sqrt(min(1.0, gia_tri_a)))


def doi_sang_thoi_diem_utc(gia_tri: str | pd.Timestamp):
    thoi_diem = pd.Timestamp(gia_tri)
    if thoi_diem.tzinfo is None:
        thoi_diem = thoi_diem.tz_localize("UTC")
    else:
        thoi_diem = thoi_diem.tz_convert("UTC")
    return thoi_diem


def dinh_dang_utc(gia_tri):
    thoi_diem = pd.Timestamp(gia_tri)
    if thoi_diem.tzinfo is None:
        thoi_diem = thoi_diem.tz_localize("UTC")
    else:
        thoi_diem = thoi_diem.tz_convert("UTC")
    return thoi_diem.isoformat().replace("+00:00", "Z")


class KhoDuLieuThoiTiet:
    """Mở các tệp thời tiết đã chuẩn hóa một lần và trả kết quả ổn định."""

    def __init__(self, thu_muc_da_xu_ly: str | Path = THU_MUC_XU_LY_MAC_DINH):
        self.thu_muc_da_xu_ly = Path(thu_muc_da_xu_ly)
        cac_duong_dan = {
            "wind": self.thu_muc_da_xu_ly / "wind.nc",
            "waves": self.thu_muc_da_xu_ly / "waves.nc",
            "currents": self.thu_muc_da_xu_ly / "currents.nc",
        }
        cac_tep_thieu = [str(duong_dan) for duong_dan in cac_duong_dan.values() if not duong_dan.exists()]
        if cac_tep_thieu:
            raise FileNotFoundError(
                "Normalized data missing. Run src/normalize_data.py first: " + ", ".join(cac_tep_thieu)
            )
        self.cac_bo_du_lieu = {ten: xr.open_dataset(duong_dan) for ten, duong_dan in cac_duong_dan.items()}

    def dong(self):
        for bo_du_lieu in self.cac_bo_du_lieu.values():
            bo_du_lieu.close()

    def __enter__(self):
        return self

    def __exit__(self, loai_ngoai_le, gia_tri_ngoai_le, vet_loi):
        self.dong()

    @staticmethod
    def tra_cuu(
        bo_du_lieu: xr.Dataset,
        cac_bien: tuple[str, ...],
        vi_do: float,
        kinh_do: float,
        thoi_diem_truy_van: pd.Timestamp,
        khoang_cach_tim_o_hop_le_toi_da_nm=None,
    ):
        gioi_han = {
            "latitude": (float(bo_du_lieu.latitude.min()), float(bo_du_lieu.latitude.max())),
            "longitude": (float(bo_du_lieu.longitude.min()), float(bo_du_lieu.longitude.max())),
            "time": (
                doi_sang_thoi_diem_utc(bo_du_lieu.time.values[0]),
                doi_sang_thoi_diem_utc(bo_du_lieu.time.values[-1]),
            ),
        }
        cac_loi = []
        if not gioi_han["latitude"][0] <= vi_do <= gioi_han["latitude"][1]:
            cac_loi.append("latitude_out_of_range")
        if not gioi_han["longitude"][0] <= kinh_do <= gioi_han["longitude"][1]:
            cac_loi.append("longitude_out_of_range")
        if not gioi_han["time"][0] <= thoi_diem_truy_van <= gioi_han["time"][1]:
            cac_loi.append("time_out_of_range")
        if cac_loi:
            return {
                "valid": False,
                "values": {},
                "errors": cac_loi,
                "notes": [],
                "matched": None,
            }

        thoi_diem_khong_mui_gio = thoi_diem_truy_van.tz_localize(None).to_datetime64()
        phan_da_chon = bo_du_lieu.sel(
            latitude=vi_do,
            longitude=kinh_do,
            time=thoi_diem_khong_mui_gio,
            method="nearest",
        )
        phuong_phap_chon = "nearest_grid_cell"
        khoang_cach_o_nguon_nm = tinh_khoang_cach_cau_nm(
            vi_do,
            kinh_do,
            float(phan_da_chon.latitude.values),
            float(phan_da_chon.longitude.values),
        )
        cac_ghi_chu = []

        co_bien_thieu = any(
            not np.isfinite(float(phan_da_chon[bien].values)) for bien in cac_bien
        )
        if co_bien_thieu and khoang_cach_tim_o_hop_le_toi_da_nm is not None:
            tai_thoi_diem = bo_du_lieu.sel(
                time=thoi_diem_khong_mui_gio, method="nearest"
            )
            mat_na_hop_le = np.ones(
                (tai_thoi_diem.sizes["latitude"], tai_thoi_diem.sizes["longitude"]),
                dtype=bool,
            )
            for bien in cac_bien:
                mat_na_hop_le &= np.isfinite(np.asarray(tai_thoi_diem[bien].values))

            cac_vi_tri_hop_le = np.argwhere(mat_na_hop_le)
            o_tot_nhat = None
            for chi_so_vi_do, chi_so_kinh_do in cac_vi_tri_hop_le:
                vi_do_o = float(tai_thoi_diem.latitude.values[chi_so_vi_do])
                kinh_do_o = float(tai_thoi_diem.longitude.values[chi_so_kinh_do])
                khoang_cach_nm = tinh_khoang_cach_cau_nm(
                    vi_do, kinh_do, vi_do_o, kinh_do_o
                )
                if o_tot_nhat is None or khoang_cach_nm < o_tot_nhat[0]:
                    o_tot_nhat = (
                        khoang_cach_nm,
                        int(chi_so_vi_do),
                        int(chi_so_kinh_do),
                    )

            if (
                o_tot_nhat is not None
                and o_tot_nhat[0] <= float(khoang_cach_tim_o_hop_le_toi_da_nm)
            ):
                khoang_cach_o_nguon_nm = o_tot_nhat[0]
                phan_da_chon = tai_thoi_diem.isel(
                    latitude=o_tot_nhat[1], longitude=o_tot_nhat[2]
                )
                phuong_phap_chon = "nearest_valid_sea_cell"
                cac_ghi_chu.append(
                    "nearest_valid_sea_cell:"
                    f"{khoang_cach_o_nguon_nm:.3f}nm"
                )
        cac_gia_tri = {}
        cac_bien_thieu = []
        for bien in cac_bien:
            gia_tri = float(phan_da_chon[bien].values)
            if np.isfinite(gia_tri):
                cac_gia_tri[bien] = gia_tri
            else:
                cac_gia_tri[bien] = None
                cac_bien_thieu.append(bien)

        return {
            "valid": not cac_bien_thieu,
            "values": cac_gia_tri,
            "errors": [f"missing:{ten}" for ten in cac_bien_thieu],
            "notes": cac_ghi_chu,
            "matched": {
                "latitude": float(phan_da_chon.latitude.values),
                "longitude": float(phan_da_chon.longitude.values),
                "time_utc": dinh_dang_utc(phan_da_chon.time.values),
                "selection_method": phuong_phap_chon,
                "distance_from_query_nm": round(khoang_cach_o_nguon_nm, 6),
            },
        }

    def weather_at(self, vi_do: float, kinh_do: float, thoi_gian_utc: str | pd.Timestamp):
        cac_ghi_chu: list[str] = []
        if not -90.0 <= float(vi_do) <= 90.0:
            return self.tao_ket_qua_khong_hop_le("latitude_invalid")
        if not -180.0 <= float(kinh_do) <= 180.0:
            return self.tao_ket_qua_khong_hop_le("longitude_invalid")
        try:
            thoi_diem_truy_van = doi_sang_thoi_diem_utc(thoi_gian_utc)
        except Exception as loi:
            return self.tao_ket_qua_khong_hop_le(f"time_invalid:{loi}")

        gio = self.tra_cuu(self.cac_bo_du_lieu["wind"], ("u10", "v10"), vi_do, kinh_do, thoi_diem_truy_van)
        song = self.tra_cuu(
            self.cac_bo_du_lieu["waves"],
            ("swh",),
            vi_do,
            kinh_do,
            thoi_diem_truy_van,
            khoang_cach_tim_o_hop_le_toi_da_nm=KHOANG_CACH_TIM_O_SONG_HOP_LE_TOI_DA_NM,
        )
        dong_chay = self.tra_cuu(self.cac_bo_du_lieu["currents"], ("uo", "vo"), vi_do, kinh_do, thoi_diem_truy_van)

        for ten_nhom, ket_qua_tra_cuu in (("wind", gio), ("waves", song)):
            cac_ghi_chu.extend(f"{ten_nhom}:{loi}" for loi in ket_qua_tra_cuu["errors"])
            cac_ghi_chu.extend(
                f"{ten_nhom}:{ghi_chu}"
                for ghi_chu in ket_qua_tra_cuu.get("notes", [])
            )
        if not dong_chay["valid"]:
            cac_ghi_chu.extend(f"currents_optional:{loi}" for loi in dong_chay["errors"])

        du_lieu_bat_buoc_hop_le = gio["valid"] and song["valid"]
        return {
            "wave_hs_m": song["values"].get("swh"),
            "wind_u_mps": gio["values"].get("u10"),
            "wind_v_mps": gio["values"].get("v10"),
            "current_u_mps": dong_chay["values"].get("uo"),
            "current_v_mps": dong_chay["values"].get("vo"),
            "valid": du_lieu_bat_buoc_hop_le,
            "note": "; ".join(cac_ghi_chu) if cac_ghi_chu else "ok",
            "query": {"latitude": float(vi_do), "longitude": float(kinh_do), "time_utc": dinh_dang_utc(thoi_diem_truy_van)},
            "source": {
                "wind": gio["matched"],
                "waves": song["matched"],
                "currents": dong_chay["matched"],
            },
        }

    @staticmethod
    def tao_ket_qua_khong_hop_le(ghi_chu: str):
        return {
            "wave_hs_m": None,
            "wind_u_mps": None,
            "wind_v_mps": None,
            "current_u_mps": None,
            "current_v_mps": None,
            "valid": False,
            "note": ghi_chu,
            "query": None,
            "source": {"wind": None, "waves": None, "currents": None},
        }


def weather_at(
    vi_do: float,
    kinh_do: float,
    thoi_gian_utc: str | pd.Timestamp,
    thu_muc_da_xu_ly: str | Path = THU_MUC_XU_LY_MAC_DINH,
):
    """Giao diện tiện dụng tuân theo hợp đồng dữ liệu STEP 2."""
    with KhoDuLieuThoiTiet(thu_muc_da_xu_ly) as kho_du_lieu:
        return kho_du_lieu.weather_at(vi_do, kinh_do, thoi_gian_utc)
