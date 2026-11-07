"""In dữ liệu NetCDF đã chuẩn hóa thành bảng trên Terminal.

Ví dụ:
    python tests/print_processed_data.py --rows 20
    python tests/print_processed_data.py --file currents --all

Tùy chọn --all có thể in hàng trăm nghìn dòng và chỉ nên dùng
khi thật sự cần hiển thị toàn bộ dữ liệu trên Terminal.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import xarray as xr


THU_MUC_GOC = Path(__file__).resolve().parents[1]
THU_MUC_DA_XU_LY = THU_MUC_GOC / "data" / "processed"

CAC_TEP_DU_LIEU = {
    "wind": THU_MUC_DA_XU_LY / "wind.nc",
    "waves": THU_MUC_DA_XU_LY / "waves.nc",
    "currents": THU_MUC_DA_XU_LY / "currents.nc",
}


def doc_tham_so_dong_lenh():
    bo_phan_tich = argparse.ArgumentParser(
        description="Print normalized STEP 2 NetCDF files as complete tables."
    )
    bo_phan_tich.add_argument(
        "--file",
        choices=("all", "wind", "waves", "currents"),
        default="all",
        help="Select one processed file or all three (default: all).",
    )
    bo_phan_tich.add_argument(
        "--rows",
        type=int,
        default=20,
        help="Rows printed per file when --all is not used (default: 20).",
    )
    bo_phan_tich.add_argument(
        "--all",
        action="store_true",
        help="Print every row, including rows containing NaN.",
    )
    return bo_phan_tich.parse_args()


def tao_bang_du_lieu(duong_dan: Path):
    if not duong_dan.exists():
        raise FileNotFoundError(
            f"Missing {duong_dan}. Run src/normalize_data.py first."
        )
    with xr.open_dataset(duong_dan) as bo_du_lieu:
        # Nạp dữ liệu trước khi đóng tệp để bảng trả về vẫn chứa đầy đủ dữ liệu.
        bang_du_lieu = bo_du_lieu.to_dataframe().reset_index()

    cac_cot_uu_tien = [
        ten
        for ten in ("time", "latitude", "longitude", "u10", "v10", "swh", "uo", "vo")
        if ten in bang_du_lieu.columns
    ]
    cac_cot_con_lai = [ten for ten in bang_du_lieu.columns if ten not in cac_cot_uu_tien]
    return bang_du_lieu[cac_cot_uu_tien + cac_cot_con_lai]


def in_bang_du_lieu(ten: str, duong_dan: Path, cac_dong: int, in_toan_bo: bool):
    bang_du_lieu = tao_bang_du_lieu(duong_dan)
    phan_da_chon = bang_du_lieu if in_toan_bo else bang_du_lieu.head(cac_dong)
    print("=" * 100)
    print(f"DATASET       : {ten}")
    print(f"FILE          : {duong_dan}")
    print(f"TOTAL ROWS    : {len(bang_du_lieu)}")
    print(f"PRINTED ROWS  : {len(phan_da_chon)}")
    print(f"COLUMNS       : {list(bang_du_lieu.columns)}")
    print("-" * 100)
    print(phan_da_chon.to_string(index=False, na_rep="NaN"))


def main():
    tham_so = doc_tham_so_dong_lenh()
    if tham_so.rows <= 0:
        raise ValueError("--rows must be greater than zero")

    cac_tep_da_chon = CAC_TEP_DU_LIEU if tham_so.file == "all" else {tham_so.file: CAC_TEP_DU_LIEU[tham_so.file]}
    for ten, duong_dan in cac_tep_da_chon.items():
        in_bang_du_lieu(ten, duong_dan, tham_so.rows, tham_so.all)

    print("=" * 100)
    if tham_so.all:
        print("Complete table output finished.")
    else:
        print("Preview finished. Add --all to print every row.")


if __name__ == "__main__":
    main()
