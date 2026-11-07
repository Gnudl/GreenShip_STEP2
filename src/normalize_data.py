"""Chuẩn hóa dữ liệu thời tiết GreenShip STEP 2 mà không điền giá trị thiếu."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import xarray as xr


THU_MUC_GOC = Path(__file__).resolve().parents[1]
THU_MUC_DU_LIEU_GOC = THU_MUC_GOC / "data" / "raw"
THU_MUC_DA_XU_LY = THU_MUC_GOC / "data" / "processed"

CAC_BO_DU_LIEU = {
    "wind": {
        "input": THU_MUC_DU_LIEU_GOC / "era5_wind_20241010_20241014.nc",
        "output": THU_MUC_DA_XU_LY / "wind.nc",
        "variables": ("u10", "v10"),
    },
    "waves": {
        "input": THU_MUC_DU_LIEU_GOC / "era5_waves_20241010_20241014.nc",
        "output": THU_MUC_DA_XU_LY / "waves.nc",
        "variables": ("swh",),
    },
    "currents": {
        "input": THU_MUC_DU_LIEU_GOC / "cmems_currents_daily_20241010_20241014_surface.nc",
        "output": THU_MUC_DA_XU_LY / "currents.nc",
        "variables": ("uo", "vo"),
    },
}

DON_VI_CHUAN = {
    "u10": "m s-1",
    "v10": "m s-1",
    "swh": "m",
    "uo": "m s-1",
    "vo": "m s-1",
}


def dinh_dang_utc(gia_tri: np.datetime64):
    return f"{np.datetime_as_string(gia_tri, unit='s')}Z"


def chuan_hoa_mot_bo(ten: str, dac_ta: dict):
    duong_dan_dau_vao: Path = dac_ta["input"]
    duong_dan_ket_qua: Path = dac_ta["output"]
    cac_bien: tuple[str, ...] = dac_ta["variables"]
    if not duong_dan_dau_vao.exists():
        raise FileNotFoundError(f"Missing raw dataset: {duong_dan_dau_vao}")

    with xr.open_dataset(duong_dan_dau_vao) as du_lieu_tho:
        bo_du_lieu = du_lieu_tho.load()

    if "valid_time" in bo_du_lieu.coords:
        bo_du_lieu = bo_du_lieu.rename({"valid_time": "time"})
    cac_toa_do_bat_buoc = {"time", "latitude", "longitude"}
    cac_toa_do_thieu = cac_toa_do_bat_buoc.difference(bo_du_lieu.coords)
    if cac_toa_do_thieu:
        raise ValueError(f"{ten}: missing coordinates {sorted(cac_toa_do_thieu)}")

    cac_bien_thieu = set(cac_bien).difference(bo_du_lieu.data_vars)
    if cac_bien_thieu:
        raise ValueError(f"{ten}: missing variables {sorted(cac_bien_thieu)}")

    bo_du_lieu = bo_du_lieu[list(cac_bien)]
    if "depth" in bo_du_lieu.dims:
        do_sau_mat = float(bo_du_lieu["depth"].values[0])
        bo_du_lieu = bo_du_lieu.isel(depth=0, drop=True)
        bo_du_lieu.attrs["selected_surface_depth_m"] = do_sau_mat

    bo_du_lieu = bo_du_lieu.sortby("time").sortby("latitude").sortby("longitude")
    if np.any(np.diff(bo_du_lieu["time"].values) < np.timedelta64(0, "ns")):
        raise ValueError(f"{ten}: time is not monotonic")

    for bien in cac_bien:
        don_vi_goc = bo_du_lieu[bien].attrs.get("units", "UNKNOWN")
        bo_du_lieu[bien].attrs["original_units"] = don_vi_goc
        bo_du_lieu[bien].attrs["units"] = DON_VI_CHUAN[bien]

    bo_du_lieu["time"].attrs.update({"timezone": "UTC", "standard_name": "time"})
    bo_du_lieu["latitude"].attrs.setdefault("units", "degrees_north")
    bo_du_lieu["longitude"].attrs.setdefault("units", "degrees_east")
    bo_du_lieu.attrs.update(
        {
            "processing_level": "GreenShip STEP 2 normalized subset",
            "missing_value_policy": "Missing values retained as NaN; never filled with zero.",
            "source_file": str(duong_dan_dau_vao.relative_to(THU_MUC_GOC)).replace("\\", "/"),
        }
    )

    duong_dan_ket_qua.parent.mkdir(parents=True, exist_ok=True)
    encoding = {
        bien: {"zlib": True, "complevel": 4, "dtype": "float32"}
        for bien in cac_bien
    }
    bo_du_lieu.to_netcdf(duong_dan_ket_qua, engine="netcdf4", encoding=encoding)

    thong_ke_bien = {}
    for bien in cac_bien:
        cac_gia_tri = np.asarray(bo_du_lieu[bien].values)
        mat_na_huu_han = np.isfinite(cac_gia_tri)
        thong_ke_bien[bien] = {
            "unit": bo_du_lieu[bien].attrs["units"],
            "minimum": float(np.nanmin(cac_gia_tri)) if mat_na_huu_han.any() else None,
            "maximum": float(np.nanmax(cac_gia_tri)) if mat_na_huu_han.any() else None,
            "missing_percent": round(100.0 * (1.0 - mat_na_huu_han.mean()), 6),
        }

    return {
        "dataset": ten,
        "input": str(duong_dan_dau_vao.relative_to(THU_MUC_GOC)).replace("\\", "/"),
        "output": str(duong_dan_ket_qua.relative_to(THU_MUC_GOC)).replace("\\", "/"),
        "sizes": dict(bo_du_lieu.sizes),
        "time_start_utc": dinh_dang_utc(bo_du_lieu["time"].values[0]),
        "time_end_utc": dinh_dang_utc(bo_du_lieu["time"].values[-1]),
        "latitude_min": float(bo_du_lieu["latitude"].min()),
        "latitude_max": float(bo_du_lieu["latitude"].max()),
        "longitude_min": float(bo_du_lieu["longitude"].min()),
        "longitude_max": float(bo_du_lieu["longitude"].max()),
        "variables": thong_ke_bien,
    }


def main():
    # Cau hinh Terminal UTF-8 de hien thi tieng Viet co dau.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cac_bao_cao = [chuan_hoa_mot_bo(ten, dac_ta) for ten, dac_ta in CAC_BO_DU_LIEU.items()]
    duong_dan_bao_cao = THU_MUC_GOC / "outputs" / "normalization_report.json"
    duong_dan_bao_cao.parent.mkdir(parents=True, exist_ok=True)
    duong_dan_bao_cao.write_text(json.dumps(cac_bao_cao, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(cac_bao_cao, indent=2, ensure_ascii=False))
    print(f"Wrote {duong_dan_bao_cao}")


if __name__ == "__main__":
    main()
