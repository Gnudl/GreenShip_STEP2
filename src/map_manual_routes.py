"""Vẽ ba tuyến thủ công STEP 2 trên nền đất liền Natural Earth."""

import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import yaml

from map_domain import doc_cac_vong_da_giac, giao_voi_pham_vi


THU_MUC_GOC = Path(__file__).resolve().parents[1]
TEP_TUYEN = THU_MUC_GOC / "data" / "routes" / "manual_routes.json"
TEP_SHAPEFILE = THU_MUC_GOC / "data" / "land" / "ne_10m_land" / "ne_10m_land.shp"
TEP_KICH_BAN = THU_MUC_GOC / "config" / "scenario.yaml"
TEP_KET_QUA = THU_MUC_GOC / "outputs" / "maps" / "manual_routes.png"


def doc_cac_tuyen_ve_ban_do(duong_dan):
    """Đọc danh sách tuyến phục vụ việc vẽ bản đồ."""
    if not duong_dan.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp tuyến: {duong_dan}")

    noi_dung = json.loads(duong_dan.read_text(encoding="utf-8"))
    cac_tuyen = noi_dung.get("routes", [])
    if not cac_tuyen:
        raise ValueError("Tệp manual_routes.json không chứa tuyến nào")

    for tuyen in cac_tuyen:
        if "route_id" not in tuyen or "waypoints" not in tuyen:
            raise ValueError("Mỗi tuyến phải có route_id và waypoints")
        if len(tuyen["waypoints"]) < 2:
            raise ValueError(f"Tuyến {tuyen['route_id']} phải có ít nhất hai waypoint")
    return cac_tuyen


def noi_suy_diem_tren_cung(diem_dau, diem_cuoi, ti_le):
    """Nội suy một điểm trên cung đường tròn lớn giữa hai waypoint."""
    if ti_le <= 0:
        return diem_dau
    if ti_le >= 1:
        return diem_cuoi

    kinh_do_1, vi_do_1 = map(math.radians, diem_dau)
    kinh_do_2, vi_do_2 = map(math.radians, diem_cuoi)
    vecto_1 = (
        math.cos(vi_do_1) * math.cos(kinh_do_1),
        math.cos(vi_do_1) * math.sin(kinh_do_1),
        math.sin(vi_do_1),
    )
    vecto_2 = (
        math.cos(vi_do_2) * math.cos(kinh_do_2),
        math.cos(vi_do_2) * math.sin(kinh_do_2),
        math.sin(vi_do_2),
    )
    tich_vo_huong = sum(a * b for a, b in zip(vecto_1, vecto_2))
    tich_vo_huong = max(-1, min(1, tich_vo_huong))
    goc = math.acos(tich_vo_huong)
    if goc == 0:
        return diem_dau

    sin_goc = math.sin(goc)
    trong_so_1 = math.sin((1 - ti_le) * goc) / sin_goc
    trong_so_2 = math.sin(ti_le * goc) / sin_goc
    x = trong_so_1 * vecto_1[0] + trong_so_2 * vecto_2[0]
    y = trong_so_1 * vecto_1[1] + trong_so_2 * vecto_2[1]
    z = trong_so_1 * vecto_1[2] + trong_so_2 * vecto_2[2]
    kinh_do = math.degrees(math.atan2(y, x))
    vi_do = math.degrees(math.atan2(z, math.hypot(x, y)))
    return kinh_do, vi_do


def tao_cac_diem_ve_tuyen(cac_diem_tuyen, so_khoang_moi_doan=30):
    """Tạo đường vẽ theo cung địa cầu và giữ waypoint chung một lần."""
    cac_diem_ve = []
    for chi_so, (diem_dau, diem_cuoi) in enumerate(
        zip(cac_diem_tuyen, cac_diem_tuyen[1:])
    ):
        cac_diem_doan = [
            noi_suy_diem_tren_cung(diem_dau, diem_cuoi, buoc / so_khoang_moi_doan)
            for buoc in range(so_khoang_moi_doan + 1)
        ]
        cac_diem_ve.extend(cac_diem_doan if chi_so == 0 else cac_diem_doan[1:])
    return cac_diem_ve


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cac_tuyen = doc_cac_tuyen_ve_ban_do(TEP_TUYEN)
    cac_vong_da_giac = doc_cac_vong_da_giac(TEP_SHAPEFILE)
    kich_ban = yaml.safe_load(TEP_KICH_BAN.read_text(encoding="utf-8"))
    pham_vi = kich_ban["data_contract"]["bounding_box"]
    phia_tay = float(pham_vi["west"])
    phia_dong = float(pham_vi["east"])
    phia_nam = float(pham_vi["south"])
    phia_bac = float(pham_vi["north"])

    cac_kieu_duong = {
        "R01": {"color": "#1565c0", "linestyle": "-", "label": "R01 - Tuyến cơ sở"},
        "R02": {"color": "#c62828", "linestyle": "--", "label": "R02 - Tuyến cố ý cắt đất"},
        "R03": {"color": "#2e7d32", "linestyle": "-.", "label": "R03 - Tuyến thay thế ngoài khơi"},
    }

    hinh, truc = plt.subplots(figsize=(8.5, 10))
    truc.set_facecolor("#dbeef7")

    for vong_da_giac in cac_vong_da_giac:
        if giao_voi_pham_vi(vong_da_giac, phia_tay, phia_dong, phia_nam, phia_bac):
            truc.fill(
                [diem[0] for diem in vong_da_giac],
                [diem[1] for diem in vong_da_giac],
                facecolor="#d9c8a9",
                edgecolor="#6f604a",
                linewidth=0.4,
                zorder=1,
            )

    for tuyen in cac_tuyen:
        kieu_duong = cac_kieu_duong.get(
            tuyen["route_id"],
            {"color": "#555555", "linestyle": "-", "label": tuyen["route_id"]},
        )
        cac_diem_ve = tao_cac_diem_ve_tuyen(tuyen["waypoints"])
        cac_kinh_do = [diem[0] for diem in cac_diem_ve]
        cac_vi_do = [diem[1] for diem in cac_diem_ve]
        truc.plot(
            cac_kinh_do,
            cac_vi_do,
            color=kieu_duong["color"],
            linestyle=kieu_duong["linestyle"],
            linewidth=2.0,
            label=kieu_duong["label"],
            zorder=3,
        )
        truc.scatter(
            [diem[0] for diem in tuyen["waypoints"]],
            [diem[1] for diem in tuyen["waypoints"]],
            color=kieu_duong["color"],
            s=14,
            zorder=4,
        )

    diem_di = cac_tuyen[0]["waypoints"][0]
    diem_den = cac_tuyen[0]["waypoints"][-1]
    truc.scatter(
        [diem_di[0], diem_den[0]],
        [diem_di[1], diem_den[1]],
        color=["#6a1b9a", "#ef6c00"],
        edgecolor="white",
        linewidth=0.8,
        s=75,
        zorder=4,
    )
    truc.annotate("Điểm tiếp cận Hải Phòng", diem_di, xytext=(7, 7), textcoords="offset points")
    truc.annotate("Điểm tiếp cận Cái Mép", diem_den, xytext=(7, -16), textcoords="offset points")

    truc.set_xlim(phia_tay, phia_dong)
    truc.set_ylim(phia_nam, phia_bac)
    truc.set_xlabel("Kinh độ")
    truc.set_ylabel("Vĩ độ")
    truc.set_title("Ba tuyến thủ công của STEP 2")
    truc.grid(color="white", linewidth=0.7, alpha=0.85)
    truc.legend(loc="upper right")
    hinh.text(
        0.01,
        0.01,
        "Các tuyến phục vụ nghiên cứu; R02 cố ý không hợp lệ; không dùng để dẫn đường.",
        fontsize=8.5,
    )

    TEP_KET_QUA.parent.mkdir(parents=True, exist_ok=True)
    hinh.savefig(TEP_KET_QUA, dpi=180, bbox_inches="tight")
    plt.close(hinh)
    print(f"Đã tạo bản đồ: {TEP_KET_QUA}")


if __name__ == "__main__":
    main()
