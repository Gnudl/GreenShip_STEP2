"""Đọc và hiển thị ba tệp NetCDF STEP 2 đã chuẩn hóa."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


THU_MUC_GOC = Path(__file__).resolve().parents[1]
THU_MUC_DA_XU_LY = THU_MUC_GOC / "data" / "processed"

CAC_TEP_DU_LIEU = (
    THU_MUC_DA_XU_LY / "wind.nc",
    THU_MUC_DA_XU_LY / "waves.nc",
    THU_MUC_DA_XU_LY / "currents.nc",
)


def chuoi_utc(gia_tri):
    thoi_diem = pd.Timestamp(gia_tri)
    if thoi_diem.tzinfo is None:
        thoi_diem = thoi_diem.tz_localize("UTC")
    else:
        thoi_diem = thoi_diem.tz_convert("UTC")
    return thoi_diem.isoformat().replace("+00:00", "Z")


def doc_tep(duong_dan: Path):
    if not duong_dan.exists():
        raise FileNotFoundError(
            f"Missing {duong_dan}. Run src/normalize_data.py first."
        )

    with xr.open_dataset(duong_dan) as bo_du_lieu:
        print("=" * 78)
        print(f"FILE       : {duong_dan.name}")
        print(f"PATH       : {duong_dan}")
        print(f"DIMENSIONS : {dict(bo_du_lieu.sizes)}")
        print(f"COORDS     : {list(bo_du_lieu.coords)}")
        print(
            "TIME UTC   : "
            f"{chuoi_utc(bo_du_lieu.time.values[0])} -> "
            f"{chuoi_utc(bo_du_lieu.time.values[-1])}"
        )
        print(
            "LATITUDE   : "
            f"{float(bo_du_lieu.latitude.min()):.6f} -> "
            f"{float(bo_du_lieu.latitude.max()):.6f}"
        )
        print(
            "LONGITUDE  : "
            f"{float(bo_du_lieu.longitude.min()):.6f} -> "
            f"{float(bo_du_lieu.longitude.max()):.6f}"
        )
        if "selected_surface_depth_m" in bo_du_lieu.attrs:
            print(f"DEPTH      : {bo_du_lieu.attrs['selected_surface_depth_m']} m")

        print("VARIABLES:")
        for ten, du_lieu in bo_du_lieu.data_vars.items():
            cac_gia_tri = np.asarray(du_lieu.values)
            mat_na_huu_han = np.isfinite(cac_gia_tri)
            so_gia_tri_thieu = int(cac_gia_tri.size - mat_na_huu_han.sum())
            ty_le_thieu = 100.0 * so_gia_tri_thieu / cac_gia_tri.size
            gia_tri_nho_nhat = float(np.nanmin(cac_gia_tri)) if mat_na_huu_han.any() else None
            gia_tri_lon_nhat = float(np.nanmax(cac_gia_tri)) if mat_na_huu_han.any() else None
            print(f"  - {ten}")
            print(f"      dims             : {du_lieu.dims}")
            print(f"      shape            : {du_lieu.shape}")
            print(f"      unit             : {du_lieu.attrs.get('units', 'UNKNOWN')}")
            print(f"      original unit    : {du_lieu.attrs.get('original_units', 'UNKNOWN')}")
            print(f"      min / max        : {gia_tri_nho_nhat} / {gia_tri_lon_nhat}")
            print(f"      missing          : {so_gia_tri_thieu}/{cac_gia_tri.size} ({ty_le_thieu:.2f}%)")


def main():
    for duong_dan_tep in CAC_TEP_DU_LIEU:
        doc_tep(duong_dan_tep)
    print("=" * 78)
    print("Successfully read all 3 normalized data files.")


if __name__ == "__main__":
    main()
