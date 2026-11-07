"""Kiểm tra các tệp NetCDF gốc được dùng trong GreenShip STEP 2.

Chương trình chỉ đọc tệp, không sửa dữ liệu và ghi thông tin có cấu trúc
cùng thống kê chất lượng vào outputs/. Giá trị thiếu vẫn được giữ nguyên.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt


THU_MUC_GOC = Path(__file__).resolve().parents[1]
THU_MUC_DU_LIEU_GOC = THU_MUC_GOC / "data" / "raw"
THU_MUC_KET_QUA = THU_MUC_GOC / "outputs"

CAC_DAU_VAO = {
    "wind": THU_MUC_DU_LIEU_GOC / "era5_wind_20241010_20241014.nc",
    "waves": THU_MUC_DU_LIEU_GOC / "era5_waves_20241010_20241014.nc",
    "currents": THU_MUC_DU_LIEU_GOC / "cmems_currents_daily_20241010_20241014_surface.nc",
}


def chuyen_gia_tri_don(gia_tri):
    if isinstance(gia_tri, (np.datetime64, pd.Timestamp)):
        thoi_diem = pd.Timestamp(gia_tri)
        if thoi_diem.tzinfo is None:
            return f"{thoi_diem.isoformat()}Z"
        return thoi_diem.tz_convert("UTC").isoformat().replace("+00:00", "Z")
    if hasattr(gia_tri, "item"):
        gia_tri = gia_tri.item()
    if isinstance(gia_tri, (np.floating, float)):
        return float(gia_tri)
    if isinstance(gia_tri, (np.integer, int)):
        return int(gia_tri)
    return str(gia_tri)


def tim_ten_toa_do(bo_du_lieu_tho: xr.Dataset, cac_ten_ung_vien: tuple[str, ...]):
    return next((ten for ten in cac_ten_ung_vien if ten in bo_du_lieu_tho.coords), None)


def kiem_tra_tep(nhom: str, duong_dan: Path):
    if not duong_dan.exists():
        raise FileNotFoundError(f"Missing required input: {duong_dan}")

    cac_dong: list[dict] = []
    with xr.open_dataset(duong_dan) as bo_du_lieu_tho:
        ten_thoi_gian = tim_ten_toa_do(bo_du_lieu_tho, ("time", "valid_time"))
        ten_vi_do = tim_ten_toa_do(bo_du_lieu_tho, ("latitude", "lat"))
        ten_kinh_do = tim_ten_toa_do(bo_du_lieu_tho, ("longitude", "lon"))
        ten_do_sau = tim_ten_toa_do(bo_du_lieu_tho, ("depth",))

        thong_tin_chung = {
            "group": nhom,
            "local_file": str(duong_dan.relative_to(THU_MUC_GOC)).replace("\\", "/"),
            "dimensions": json.dumps(dict(bo_du_lieu_tho.sizes), sort_keys=True),
            "time_coordinate": ten_thoi_gian,
            "time_start_utc": chuyen_gia_tri_don(bo_du_lieu_tho[ten_thoi_gian].min().values) if ten_thoi_gian else None,
            "time_end_utc": chuyen_gia_tri_don(bo_du_lieu_tho[ten_thoi_gian].max().values) if ten_thoi_gian else None,
            "latitude_min": chuyen_gia_tri_don(bo_du_lieu_tho[ten_vi_do].min().values) if ten_vi_do else None,
            "latitude_max": chuyen_gia_tri_don(bo_du_lieu_tho[ten_vi_do].max().values) if ten_vi_do else None,
            "longitude_min": chuyen_gia_tri_don(bo_du_lieu_tho[ten_kinh_do].min().values) if ten_kinh_do else None,
            "longitude_max": chuyen_gia_tri_don(bo_du_lieu_tho[ten_kinh_do].max().values) if ten_kinh_do else None,
            "depth_m": chuyen_gia_tri_don(bo_du_lieu_tho[ten_do_sau].values[0]) if ten_do_sau else None,
        }

        for bien, du_lieu in bo_du_lieu_tho.data_vars.items():
            cac_gia_tri = np.asarray(du_lieu.values)
            mat_na_huu_han = np.isfinite(cac_gia_tri)
            so_gia_tri_hop_le = int(mat_na_huu_han.sum())
            tong_so_gia_tri = int(cac_gia_tri.size)
            so_gia_tri_thieu = tong_so_gia_tri - so_gia_tri_hop_le
            dong = {
                **thong_tin_chung,
                "variable": bien,
                "units_original": du_lieu.attrs.get("units", "UNKNOWN"),
                "variable_dimensions": json.dumps(list(du_lieu.dims)),
                "shape": "x".join(str(size) for size in du_lieu.shape),
                "total_cells": tong_so_gia_tri,
                "valid_cells": so_gia_tri_hop_le,
                "missing_cells": so_gia_tri_thieu,
                "missing_percent": round(100.0 * so_gia_tri_thieu / tong_so_gia_tri, 6),
                "minimum": float(np.nanmin(cac_gia_tri)) if so_gia_tri_hop_le else None,
                "maximum": float(np.nanmax(cac_gia_tri)) if so_gia_tri_hop_le else None,
            }
            cac_dong.append(dong)
    return cac_dong


def ghi_hinh_kiem_tra(bang_du_lieu: pd.DataFrame):
    """Lưu bảng kết quả gọn; đây không phải ảnh chụp Terminal."""
    duong_dan_hinh = THU_MUC_KET_QUA / "data_audit_table.png"
    bang_hien_thi = bang_du_lieu[
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
    bang_hien_thi["minimum"] = bang_hien_thi["minimum"].map(lambda gia_tri: f"{gia_tri:.4f}")
    bang_hien_thi["maximum"] = bang_hien_thi["maximum"].map(lambda gia_tri: f"{gia_tri:.4f}")
    bang_hien_thi["missing_percent"] = bang_hien_thi["missing_percent"].map(lambda gia_tri: f"{gia_tri:.2f}%")
    bang_hien_thi.columns = ["Group", "Variable", "Unit", "Min", "Max", "Missing", "Start UTC", "End UTC"]

    hinh, truc = plt.subplots(figsize=(16, 4.2))
    truc.axis("off")
    truc.set_title("GreenShip STEP 2 - Raw data audit", fontsize=16, fontweight="bold", pad=18)
    bang = truc.table(
        cellText=bang_hien_thi.values,
        colLabels=bang_hien_thi.columns,
        cellLoc="center",
        loc="center",
        colWidths=[0.08, 0.07, 0.08, 0.07, 0.07, 0.08, 0.22, 0.22],
    )
    bang.auto_set_font_size(False)
    bang.set_fontsize(9)
    bang.scale(1, 1.6)
    for (dong, _cot), o_bang in bang.get_celld().items():
        if dong == 0:
            o_bang.set_facecolor("#1f4e78")
            o_bang.set_text_props(color="white", fontweight="bold")
        elif dong % 2 == 0:
            o_bang.set_facecolor("#eaf2f8")
    hinh.text(
        0.01,
        0.03,
        "Missing ocean variables mainly represent land cells; values are not filled with zero.",
        fontsize=9,
    )
    hinh.savefig(duong_dan_hinh, dpi=180, bbox_inches="tight")
    plt.close(hinh)
    return duong_dan_hinh


def main():
    THU_MUC_KET_QUA.mkdir(parents=True, exist_ok=True)
    cac_dong: list[dict] = []
    for nhom, duong_dan in CAC_DAU_VAO.items():
        cac_dong.extend(kiem_tra_tep(nhom, duong_dan))

    bang_du_lieu = pd.DataFrame(cac_dong)
    duong_dan_csv = THU_MUC_KET_QUA / "data_audit.csv"
    duong_dan_json = THU_MUC_KET_QUA / "data_audit.json"
    bang_du_lieu.to_csv(duong_dan_csv, index=False, encoding="utf-8-sig")
    duong_dan_json.write_text(json.dumps(cac_dong, indent=2, ensure_ascii=False), encoding="utf-8")
    duong_dan_hinh = ghi_hinh_kiem_tra(bang_du_lieu)

    cac_cot = [
        "group",
        "variable",
        "units_original",
        "minimum",
        "maximum",
        "missing_percent",
        "time_start_utc",
        "time_end_utc",
    ]
    print(bang_du_lieu[cac_cot].to_string(index=False))
    print(f"\nWrote {duong_dan_csv}")
    print(f"Wrote {duong_dan_json}")
    print(f"Wrote {duong_dan_hinh}")


if __name__ == "__main__":
    main()
