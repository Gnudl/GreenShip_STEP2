"""Vẽ độ cao sóng ERA5 tại giờ xuất phát và ba tuyến STEP 2."""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import xarray as xr
import yaml


def main():
    tham_so = argparse.ArgumentParser(description=__doc__)
    tham_so.add_argument("--du-an", type=Path, default=Path.cwd())
    tham_so.add_argument("--dau-ra", type=Path)
    lua_chon = tham_so.parse_args()
    goc = lua_chon.du_an.resolve()
    sys.path.insert(0, str(goc / "src"))
    from map_domain import doc_cac_vong_da_giac, giao_voi_pham_vi
    from map_manual_routes import doc_cac_tuyen_ve_ban_do, tao_cac_diem_ve_tuyen

    kich_ban = yaml.safe_load((goc / "config/scenario.yaml").read_text(encoding="utf-8"))
    thoi_diem = pd.to_datetime(kich_ban["departure_utc"], utc=True)
    pham_vi = kich_ban["data_contract"]["bounding_box"]
    tay, dong, nam, bac = [pham_vi[k] for k in ("west", "east", "south", "north")]
    with xr.open_dataset(goc / "data/processed/waves.nc") as du_lieu:
        song = du_lieu.swh.sel(time=thoi_diem.tz_localize(None)).load()
    hinh, truc = plt.subplots(figsize=(8, 9), layout="constrained")
    truc.set_facecolor("#eeeef0")
    lop_song = truc.pcolormesh(song.longitude, song.latitude, song.transpose("latitude", "longitude"),
                               cmap="YlGnBu", shading="nearest", vmin=0)
    hinh.colorbar(lop_song, ax=truc, shrink=0.65, label="Độ cao sóng có nghĩa Hs (m)")
    for vong in doc_cac_vong_da_giac(goc / "data/land/ne_10m_land/ne_10m_land.shp"):
        if giao_voi_pham_vi(vong, tay, dong, nam, bac):
            truc.fill(*zip(*vong), color="#e0d2b8", ec="#796f60", lw=0.4)
    kieu = {"R01": ("#141e3c", "-"), "R02": ("#b41e2c", "--"), "R03": ("#782389", "-.")}
    for tuyen in doc_cac_tuyen_ve_ban_do(goc / "data/routes/manual_routes.json"):
        ma = tuyen["route_id"]
        mau, net = kieu[ma]
        truc.plot(*zip(*tao_cac_diem_ve_tuyen(tuyen["waypoints"])), color=mau, ls=net, lw=2, label=ma)
    truc.set(xlim=(tay, dong), ylim=(nam, bac), xlabel="Kinh độ (°E)", ylabel="Vĩ độ (°N)",
             title=f"Ba tuyến thử và độ cao sóng tại giờ xuất phát\n{thoi_diem:%d/%m/%Y %H:%M} UTC")
    truc.legend()
    truc.text(0, -0.11, "Nguồn: ERA5 (swh), Natural Earth Land 5.1.1. Ô xám: thiếu dữ liệu sóng.",
              transform=truc.transAxes, fontsize=9)
    tep = lua_chon.dau_ra or goc / "outputs/maps/manual_routes_hs.png"
    tep.parent.mkdir(parents=True, exist_ok=True)
    hinh.savefig(tep, dpi=170, bbox_inches="tight")
    plt.close(hinh)
    print(tep.resolve())


if __name__ == "__main__":
    main()
