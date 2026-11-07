"""Vẽ miền dữ liệu STEP 2 và kiểm tra các điểm đầu cuối với polygon đất liền.

Tệp Natural Earth được đọc bằng thư viện chuẩn của Python để chương trình
không phải cài thêm gói GIS. Phần kiểm tra hình học tuyến ở bước sau
cần dùng phương pháp hình học đã được kiểm thử.
"""

from __future__ import annotations

import json
import sys
import struct
from pathlib import Path

import matplotlib.pyplot as plt
import yaml


THU_MUC_GOC = Path(__file__).resolve().parents[1]
TEP_SHAPEFILE = THU_MUC_GOC / "data" / "land" / "ne_10m_land" / "ne_10m_land.shp"
TEP_KICH_BAN = THU_MUC_GOC / "config" / "scenario.yaml"
THU_MUC_BAN_DO = THU_MUC_GOC / "outputs" / "maps"


def doc_cac_vong_da_giac(duong_dan: Path):
    """Đọc các bản ghi Polygon của shapefile ESRI thành vòng (kinh độ, vĩ độ)."""
    cac_vong_da_giac: list[list[tuple[float, float]]] = []
    with duong_dan.open("rb") as luong_tep:
        dau_tep = luong_tep.read(100)
        if len(dau_tep) != 100 or struct.unpack(">i", dau_tep[:4])[0] != 9994:
            raise ValueError(f"Invalid shapefile header: {duong_dan}")

        while True:
            dau_ban_ghi = luong_tep.read(8)
            if not dau_ban_ghi:
                break
            if len(dau_ban_ghi) != 8:
                raise ValueError("Truncated shapefile record header")
            _so_ban_ghi, do_dai_ban_ghi = struct.unpack(">2i", dau_ban_ghi)
            noi_dung_ban_ghi = luong_tep.read(do_dai_ban_ghi * 2)
            if len(noi_dung_ban_ghi) != do_dai_ban_ghi * 2:
                raise ValueError("Truncated shapefile record")

            loai_hinh = struct.unpack_from("<i", noi_dung_ban_ghi, 0)[0]
            if loai_hinh == 0:
                continue
            if loai_hinh not in (5, 15, 25):
                raise ValueError(f"Expected polygon shapefile, found shape type {loai_hinh}")

            so_phan, so_diem = struct.unpack_from("<2i", noi_dung_ban_ghi, 36)
            cac_vi_tri_phan = list(struct.unpack_from(f"<{so_phan}i", noi_dung_ban_ghi, 44))
            vi_tri_diem = 44 + so_phan * 4
            cac_diem = [
                struct.unpack_from("<2d", noi_dung_ban_ghi, vi_tri_diem + index * 16)
                for index in range(so_diem)
            ]
            cac_ranh_gioi = cac_vi_tri_phan + [so_diem]
            for diem_dau, diem_cuoi in zip(cac_ranh_gioi, cac_ranh_gioi[1:]):
                if diem_cuoi - diem_dau >= 3:
                    cac_vong_da_giac.append(cac_diem[diem_dau:diem_cuoi])
    return cac_vong_da_giac


def diem_nam_trong_vong(kinh_do: float, vi_do: float, vong_da_giac: list[tuple[float, float]]):
    nam_ben_trong = False
    kinh_do_truoc, vi_do_truoc = vong_da_giac[-1]
    for kinh_do_hien_tai, vi_do_hien_tai in vong_da_giac:
        co_giao_nhau = (vi_do_hien_tai > vi_do) != (vi_do_truoc > vi_do)
        if co_giao_nhau:
            kinh_do_giao = (kinh_do_truoc - kinh_do_hien_tai) * (vi_do - vi_do_hien_tai) / (vi_do_truoc - vi_do_hien_tai) + kinh_do_hien_tai
            if kinh_do < kinh_do_giao:
                nam_ben_trong = not nam_ben_trong
        kinh_do_truoc, vi_do_truoc = kinh_do_hien_tai, vi_do_hien_tai
    return nam_ben_trong


def diem_nam_tren_dat(kinh_do: float, vi_do: float, cac_vong_da_giac: list[list[tuple[float, float]]]):
    # Quy tắc chẵn-lẻ xử lý vòng ngoài và lỗ rỗng trên bản đồ kiểm tra.
    return sum(diem_nam_trong_vong(kinh_do, vi_do, vong_da_giac) for vong_da_giac in cac_vong_da_giac) % 2 == 1


def giao_voi_pham_vi(vong_da_giac: list[tuple[float, float]], phia_tay: float, phia_dong: float, phia_nam: float, phia_bac: float):
    cac_kinh_do = [diem[0] for diem in vong_da_giac]
    cac_vi_do = [diem[1] for diem in vong_da_giac]
    return not (max(cac_kinh_do) < phia_tay or min(cac_kinh_do) > phia_dong or max(cac_vi_do) < phia_nam or min(cac_vi_do) > phia_bac)


def main():
    # Cau hinh Terminal UTF-8 de hien thi tieng Viet co dau.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not TEP_SHAPEFILE.exists():
        raise FileNotFoundError(TEP_SHAPEFILE)
    kich_ban = yaml.safe_load(TEP_KICH_BAN.read_text(encoding="utf-8"))
    pham_vi = kich_ban["data_contract"]["bounding_box"]
    phia_tay, phia_dong = float(pham_vi["west"]), float(pham_vi["east"])
    phia_nam, phia_bac = float(pham_vi["south"]), float(pham_vi["north"])
    cac_vong_da_giac = doc_cac_vong_da_giac(TEP_SHAPEFILE)

    diem_di = kich_ban["main_route"]["origin"]
    diem_den = kich_ban["main_route"]["destination"]
    cac_diem_dau_cuoi = {
        "origin": {
            "name": diem_di["name"],
            "latitude": float(diem_di["latitude"]),
            "longitude": float(diem_di["longitude"]),
        },
        "destination": {
            "name": diem_den["name"],
            "latitude": float(diem_den["latitude"]),
            "longitude": float(diem_den["longitude"]),
        },
    }
    for diem_dau_cuoi in cac_diem_dau_cuoi.values():
        diem_dau_cuoi["natural_earth_land"] = diem_nam_tren_dat(diem_dau_cuoi["longitude"], diem_dau_cuoi["latitude"], cac_vong_da_giac)

    truong_hop_nho = kich_ban["debug_mini_case"]
    cac_diem_truong_hop_nho = [truong_hop_nho["start"], truong_hop_nho["end"]]
    trang_thai_truong_hop_nho = [
        {
            "latitude": float(diem["latitude"]),
            "longitude": float(diem["longitude"]),
            "natural_earth_land": diem_nam_tren_dat(float(diem["longitude"]), float(diem["latitude"]), cac_vong_da_giac),
        }
        for diem in cac_diem_truong_hop_nho
    ]

    THU_MUC_BAN_DO.mkdir(parents=True, exist_ok=True)
    du_lieu_xuat = {
        "shapefile": str(TEP_SHAPEFILE.relative_to(THU_MUC_GOC)).replace("\\", "/"),
        "crs": "WGS84 / EPSG:4326",
        "polygon_ring_count": len(cac_vong_da_giac),
        "endpoints": cac_diem_dau_cuoi,
        "mini_case": trang_thai_truong_hop_nho,
        "note": "Natural Earth is suitable for research screening, not operational navigation.",
    }
    duong_dan_kiem_tra = THU_MUC_GOC / "outputs" / "land_port_check.json"
    duong_dan_kiem_tra.write_text(json.dumps(du_lieu_xuat, indent=2, ensure_ascii=False), encoding="utf-8")

    hinh, truc = plt.subplots(figsize=(8.5, 10))
    for vong_da_giac in cac_vong_da_giac:
        if giao_voi_pham_vi(vong_da_giac, phia_tay, phia_dong, phia_nam, phia_bac):
            x = [diem[0] for diem in vong_da_giac]
            y = [diem[1] for diem in vong_da_giac]
            truc.fill(x, y, facecolor="#d9c8a9", edgecolor="#6f604a", linewidth=0.45, zorder=1)

    truc.set_facecolor("#dbeef7")
    truc.plot(
        [cac_diem_dau_cuoi["origin"]["longitude"], cac_diem_dau_cuoi["destination"]["longitude"]],
        [cac_diem_dau_cuoi["origin"]["latitude"], cac_diem_dau_cuoi["destination"]["latitude"]],
        linestyle="--",
        color="#697077",
        linewidth=1.1,
        label="Endpoint chord (not an accepted route)",
        zorder=2,
    )
    truc.scatter(
        [cac_diem_dau_cuoi["origin"]["longitude"], cac_diem_dau_cuoi["destination"]["longitude"]],
        [cac_diem_dau_cuoi["origin"]["latitude"], cac_diem_dau_cuoi["destination"]["latitude"]],
        color=["#1565c0", "#c62828"],
        s=55,
        zorder=3,
        label="Model endpoints",
    )
    truc.plot(
        [diem["longitude"] for diem in trang_thai_truong_hop_nho],
        [diem["latitude"] for diem in trang_thai_truong_hop_nho],
        color="#2e7d32",
        linewidth=2.2,
        marker="o",
        label="Debug mini-case",
        zorder=3,
    )
    truc.set_xlim(phia_tay, phia_dong)
    truc.set_ylim(phia_nam, phia_bac)
    truc.set_xlabel("Longitude (degrees east)")
    truc.set_ylabel("Latitude (degrees north)")
    truc.set_title("STEP 2 data domain and Natural Earth land mask")
    truc.grid(color="white", linewidth=0.7, alpha=0.8)
    truc.legend(loc="lower right")
    hinh.text(0.01, 0.01, "Research screening only — not for navigation", fontsize=9)
    duong_dan_ban_do = THU_MUC_BAN_DO / "map_domain.png"
    hinh.savefig(duong_dan_ban_do, dpi=180, bbox_inches="tight")
    plt.close(hinh)

    print(json.dumps(du_lieu_xuat, indent=2, ensure_ascii=False))
    print(f"Wrote {duong_dan_kiem_tra}")
    print(f"Wrote {duong_dan_ban_do}")


if __name__ == "__main__":
    main()
