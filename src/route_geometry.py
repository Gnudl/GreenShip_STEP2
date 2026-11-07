"""Đánh giá hình học các tuyến thủ công của GreenShip STEP 2.

Mô-đun này:
- đọc tuyến có thứ tự tọa độ [kinh độ, vĩ độ];
- tính khoảng cách trắc địa WGS84 theo hải lý;
- chia điểm trên từng đoạn theo khoảng cách tối đa đã cấu hình;
- kiểm tra toàn bộ đoạn tuyến với polygon đất liền Natural Earth;
- ghi báo cáo JSON có kết quả ổn định.

Natural Earth chỉ dùng để sàng lọc nghiên cứu, không dùng để dẫn đường.
"""

from __future__ import annotations

import argparse
import json
import sys
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from map_domain import doc_cac_vong_da_giac


THU_MUC_GOC = Path(__file__).resolve().parents[1]
TEP_TUYEN_MAC_DINH = THU_MUC_GOC / "data" / "routes" / "manual_routes.json"
TEP_SHAPEFILE_MAC_DINH = THU_MUC_GOC / "data" / "land" / "ne_10m_land" / "ne_10m_land.shp"
TEP_KICH_BAN_MAC_DINH = THU_MUC_GOC / "config" / "scenario.yaml"
TEP_KET_QUA_MAC_DINH = THU_MUC_GOC / "outputs" / "route_geometry.json"

SO_MET_MOI_HAI_LY = 1852.0
WGS84_A_M = 6_378_137.0
WGS84_F = 1.0 / 298.257223563
WGS84_B_M = (1.0 - WGS84_F) * WGS84_A_M
EPSILON = 1e-12

Diem = tuple[float, float]  # (longitude, latitude)


def kiem_tra_diem(kinh_do: float, vi_do: float):
    """Trả về điểm (kinh độ, vĩ độ) đã được kiểm tra."""
    kinh_do = float(kinh_do)
    vi_do = float(vi_do)
    if not math.isfinite(kinh_do) or not math.isfinite(vi_do):
        raise ValueError("Waypoint coordinates must be finite numbers")
    if not -180.0 <= kinh_do <= 180.0:
        raise ValueError(f"Longitude outside [-180, 180]: {kinh_do}")
    if not -90.0 <= vi_do <= 90.0:
        raise ValueError(f"Latitude outside [-90, 90]: {vi_do}")
    return kinh_do, vi_do


def doc_diem_tuyen(gia_tri: Any):
    """Chấp nhận [kinh độ, vĩ độ] hoặc đối tượng có khóa longitude/latitude."""
    if isinstance(gia_tri, dict):
        if "longitude" not in gia_tri or "latitude" not in gia_tri:
            raise ValueError("Waypoint mapping needs longitude and latitude")
        return kiem_tra_diem(gia_tri["longitude"], gia_tri["latitude"])
    if isinstance(gia_tri, (list, tuple)) and len(gia_tri) == 2:
        return kiem_tra_diem(gia_tri[0], gia_tri[1])
    raise ValueError(f"Unsupported waypoint format: {gia_tri!r}")


def doc_cac_tuyen(duong_dan: Path | str = TEP_TUYEN_MAC_DINH):
    """Đọc và kiểm tra các tuyến thủ công từ JSON."""
    duong_dan = Path(duong_dan)
    if not duong_dan.exists():
        raise FileNotFoundError(
            f"Route file not found: {duong_dan}. "
            "Create data/routes/manual_routes.json before running this script."
        )

    noi_dung = json.loads(duong_dan.read_text(encoding="utf-8"))
    cac_tuyen_tho = noi_dung.get("routes") if isinstance(noi_dung, dict) else noi_dung
    if not isinstance(cac_tuyen_tho, list) or not cac_tuyen_tho:
        raise ValueError("Route JSON must contain a non-empty 'routes' list")

    cac_tuyen: list[dict[str, Any]] = []
    cac_ma_da_gap: set[str] = set()
    for index, tuyen_tho in enumerate(cac_tuyen_tho, start=1):
        if not isinstance(tuyen_tho, dict):
            raise ValueError(f"Route {index} must be a JSON object")
        ma_tuyen = str(tuyen_tho.get("route_id", "")).strip()
        if not ma_tuyen:
            raise ValueError(f"Route {index} has no route_id")
        if ma_tuyen in cac_ma_da_gap:
            raise ValueError(f"Duplicate route_id: {ma_tuyen}")
        cac_ma_da_gap.add(ma_tuyen)

        cac_diem_tuyen_tho = tuyen_tho.get("waypoints")
        if not isinstance(cac_diem_tuyen_tho, list) or len(cac_diem_tuyen_tho) < 2:
            raise ValueError(f"Route {ma_tuyen} needs at least two waypoints")

        cac_tuyen.append(
            {
                **tuyen_tho,
                "route_id": ma_tuyen,
                "name": str(tuyen_tho.get("name", ma_tuyen)),
                "waypoints": [doc_diem_tuyen(diem) for diem in cac_diem_tuyen_tho],
            }
        )
    return cac_tuyen


def tinh_khoang_cach_haversine_m(diem_dau: Diem, diem_cuoi: Diem):
    """Dùng công thức hình cầu ổn định khi phép lặp Vincenty không hội tụ."""
    kinh_do_1, vi_do_1 = map(math.radians, diem_dau)
    kinh_do_2, vi_do_2 = map(math.radians, diem_cuoi)
    chenh_lech_vi_do = vi_do_2 - vi_do_1
    chenh_lech_kinh_do = kinh_do_2 - kinh_do_1
    gia_tri = (
        math.sin(chenh_lech_vi_do / 2.0) ** 2
        + math.cos(vi_do_1) * math.cos(vi_do_2) * math.sin(chenh_lech_kinh_do / 2.0) ** 2
    )
    return 2.0 * 6_371_008.8 * math.asin(min(1.0, math.sqrt(gia_tri)))


def tinh_khoang_cach_trac_dia_m(diem_dau: Diem, diem_cuoi: Diem):
    """Tính khoảng cách ellipsoid bằng phương pháp nghịch đảo Vincenty trên WGS84."""
    kinh_do_1, vi_do_1 = kiem_tra_diem(*diem_dau)
    kinh_do_2, vi_do_2 = kiem_tra_diem(*diem_cuoi)
    if kinh_do_1 == kinh_do_2 and vi_do_1 == vi_do_2:
        return 0.0

    phi1 = math.radians(vi_do_1)
    phi2 = math.radians(vi_do_2)
    reduced1 = math.atan((1.0 - WGS84_F) * math.tan(phi1))
    reduced2 = math.atan((1.0 - WGS84_F) * math.tan(phi2))
    sin_u1, cos_u1 = math.sin(reduced1), math.cos(reduced1)
    sin_u2, cos_u2 = math.sin(reduced2), math.cos(reduced2)
    chenh_lech_kinh_do = math.radians(kinh_do_2 - kinh_do_1)
    gia_tri_lambda = chenh_lech_kinh_do

    for _ in range(200):
        sin_lambda = math.sin(gia_tri_lambda)
        cos_lambda = math.cos(gia_tri_lambda)
        sin_sigma = math.sqrt(
            (cos_u2 * sin_lambda) ** 2
            + (cos_u1 * sin_u2 - sin_u1 * cos_u2 * cos_lambda) ** 2
        )
        if sin_sigma == 0.0:
            return 0.0
        cos_sigma = sin_u1 * sin_u2 + cos_u1 * cos_u2 * cos_lambda
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = cos_u1 * cos_u2 * sin_lambda / sin_sigma
        cos_sq_alpha = 1.0 - sin_alpha**2
        cos_two_sigma_m = (
            cos_sigma - 2.0 * sin_u1 * sin_u2 / cos_sq_alpha
            if cos_sq_alpha > EPSILON
            else 0.0
        )
        he_so = WGS84_F / 16.0 * cos_sq_alpha * (
            4.0 + WGS84_F * (4.0 - 3.0 * cos_sq_alpha)
        )
        lambda_truoc = gia_tri_lambda
        gia_tri_lambda = chenh_lech_kinh_do + (1.0 - he_so) * WGS84_F * sin_alpha * (
            sigma
            + he_so
            * sin_sigma
            * (
                cos_two_sigma_m
                + he_so
                * cos_sigma
                * (-1.0 + 2.0 * cos_two_sigma_m**2)
            )
        )
        if abs(gia_tri_lambda - lambda_truoc) <= 1e-12:
            break
    else:
        return tinh_khoang_cach_haversine_m(diem_dau, diem_cuoi)

    u_sq = cos_sq_alpha * (WGS84_A_M**2 - WGS84_B_M**2) / WGS84_B_M**2
    he_so_a = 1.0 + u_sq / 16384.0 * (
        4096.0 + u_sq * (-768.0 + u_sq * (320.0 - 175.0 * u_sq))
    )
    he_so_b = u_sq / 1024.0 * (
        256.0 + u_sq * (-128.0 + u_sq * (74.0 - 47.0 * u_sq))
    )
    chenh_lech_sigma = he_so_b * sin_sigma * (
        cos_two_sigma_m
        + he_so_b
        / 4.0
        * (
            cos_sigma * (-1.0 + 2.0 * cos_two_sigma_m**2)
            - he_so_b
            / 6.0
            * cos_two_sigma_m
            * (-3.0 + 4.0 * sin_sigma**2)
            * (-3.0 + 4.0 * cos_two_sigma_m**2)
        )
    )
    return WGS84_B_M * he_so_a * (sigma - chenh_lech_sigma)


def tinh_khoang_cach_trac_dia_nm(diem_dau: Diem, diem_cuoi: Diem):
    """Trả về khoảng cách trắc địa WGS84 theo hải lý."""
    return tinh_khoang_cach_trac_dia_m(diem_dau, diem_cuoi) / SO_MET_MOI_HAI_LY


def noi_suy_duong_tron_lon(diem_dau: Diem, diem_cuoi: Diem, ti_le: float):
    """Nội suy điểm theo cung đường tròn lớn ngắn."""
    if ti_le <= 0.0:
        return diem_dau
    if ti_le >= 1.0:
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
    tich_vo_huong = max(-1.0, min(1.0, sum(a * b for a, b in zip(vecto_1, vecto_2))))
    goc = math.acos(tich_vo_huong)
    if goc < EPSILON:
        return diem_dau
    sin_angle = math.sin(goc)
    trong_so_1 = math.sin((1.0 - ti_le) * goc) / sin_angle
    trong_so_2 = math.sin(ti_le * goc) / sin_angle
    x = trong_so_1 * vecto_1[0] + trong_so_2 * vecto_2[0]
    y = trong_so_1 * vecto_1[1] + trong_so_2 * vecto_2[1]
    z = trong_so_1 * vecto_1[2] + trong_so_2 * vecto_2[2]
    kinh_do = math.degrees(math.atan2(y, x))
    vi_do = math.degrees(math.atan2(z, math.hypot(x, y)))
    return kinh_do, vi_do


def chia_diem_tren_doan(diem_dau: Diem, diem_cuoi: Diem, khoang_cach_toi_da_nm: float = 5.0):
    """Chia điểm trên đoạn để mọi khoảng cách WGS84 liên tiếp không vượt giới hạn."""
    if khoang_cach_toi_da_nm <= 0.0:
        raise ValueError("maximum_spacing_nm must be greater than zero")
    diem_dau = kiem_tra_diem(*diem_dau)
    diem_cuoi = kiem_tra_diem(*diem_cuoi)
    khoang_cach_nm = tinh_khoang_cach_trac_dia_nm(diem_dau, diem_cuoi)
    so_khoang = max(1, math.ceil(khoang_cach_nm / khoang_cach_toi_da_nm))

    # Nội suy đường tròn lớn có sai khác rất nhỏ trên các đoạn biển ngắn.
    # Kiểm tra lại bằng WGS84 và tăng số khoảng nếu vượt giới hạn.
    while True:
        cac_diem = [
            noi_suy_duong_tron_lon(diem_dau, diem_cuoi, index / so_khoang)
            for index in range(so_khoang + 1)
        ]
        khoang_cach_lon_nhat = max(
            tinh_khoang_cach_trac_dia_nm(diem_thu_nhat, diem_thu_hai)
            for diem_thu_nhat, diem_thu_hai in zip(cac_diem, cac_diem[1:])
        )
        if khoang_cach_lon_nhat <= khoang_cach_toi_da_nm + 1e-9:
            return cac_diem
        so_khoang += 1


def chia_diem_tren_tuyen(cac_diem_tuyen: Iterable[Diem], khoang_cach_toi_da_nm: float = 5.0):
    """Chia điểm trên mọi đoạn và chỉ giữ waypoint chung một lần."""
    cac_diem = list(cac_diem_tuyen)
    if len(cac_diem) < 2:
        raise ValueError("A route needs at least two waypoints")
    cac_diem_mau: list[Diem] = []
    for index, (diem_dau, diem_cuoi) in enumerate(zip(cac_diem, cac_diem[1:])):
        cac_diem_doan = chia_diem_tren_doan(diem_dau, diem_cuoi, khoang_cach_toi_da_nm)
        cac_diem_mau.extend(cac_diem_doan if index == 0 else cac_diem_doan[1:])
    return cac_diem_mau


def tinh_khoang_cach_tuyen_nm(cac_diem_tuyen: Iterable[Diem]):
    """Cộng khoảng cách trắc địa của mọi đoạn tuyến gốc."""
    cac_diem = list(cac_diem_tuyen)
    return sum(
        tinh_khoang_cach_trac_dia_nm(diem_dau, diem_cuoi)
        for diem_dau, diem_cuoi in zip(cac_diem, cac_diem[1:])
    )


def tao_hop_bao_vong(vong_da_giac: list[Diem]):
    cac_kinh_do = [diem[0] for diem in vong_da_giac]
    cac_vi_do = [diem[1] for diem in vong_da_giac]
    return min(cac_kinh_do), max(cac_kinh_do), min(cac_vi_do), max(cac_vi_do)


def hai_hop_bao_giao_nhau(
    diem_thu_nhat: tuple[float, float, float, float],
    diem_thu_hai: tuple[float, float, float, float],
):
    return not (
        diem_thu_nhat[1] < diem_thu_hai[0]
        or diem_thu_nhat[0] > diem_thu_hai[1]
        or diem_thu_nhat[3] < diem_thu_hai[2]
        or diem_thu_nhat[2] > diem_thu_hai[3]
    )


def diem_o_trong_vong(diem: Diem, vong_da_giac: list[Diem]):
    kinh_do, vi_do = diem
    nam_ben_trong = False
    kinh_do_truoc, vi_do_truoc = vong_da_giac[-1]
    for kinh_do_hien_tai, vi_do_hien_tai in vong_da_giac:
        co_giao_nhau = (vi_do_hien_tai > vi_do) != (vi_do_truoc > vi_do)
        if co_giao_nhau:
            kinh_do_cat = (
                (kinh_do_truoc - kinh_do_hien_tai)
                * (vi_do - vi_do_hien_tai)
                / (vi_do_truoc - vi_do_hien_tai)
                + kinh_do_hien_tai
            )
            if kinh_do < kinh_do_cat:
                nam_ben_trong = not nam_ben_trong
        kinh_do_truoc, vi_do_truoc = kinh_do_hien_tai, vi_do_hien_tai
    return nam_ben_trong


def tinh_huong_ba_diem(diem_thu_nhat: Diem, diem_thu_hai: Diem, diem_thu_ba: Diem):
    return (diem_thu_hai[0] - diem_thu_nhat[0]) * (diem_thu_ba[1] - diem_thu_nhat[1]) - (
        diem_thu_hai[1] - diem_thu_nhat[1]
    ) * (diem_thu_ba[0] - diem_thu_nhat[0])


def diem_nam_tren_doan(diem_thu_nhat: Diem, diem: Diem, diem_thu_hai: Diem):
    return (
        min(diem_thu_nhat[0], diem_thu_hai[0]) - EPSILON <= diem[0] <= max(diem_thu_nhat[0], diem_thu_hai[0]) + EPSILON
        and min(diem_thu_nhat[1], diem_thu_hai[1]) - EPSILON <= diem[1] <= max(diem_thu_nhat[1], diem_thu_hai[1]) + EPSILON
        and abs(tinh_huong_ba_diem(diem_thu_nhat, diem_thu_hai, diem)) <= EPSILON
    )


def hai_doan_giao_nhau(dau_doan_thu_nhat: Diem, cuoi_doan_thu_nhat: Diem, dau_doan_thu_hai: Diem, cuoi_doan_thu_hai: Diem):
    o1 = tinh_huong_ba_diem(dau_doan_thu_nhat, cuoi_doan_thu_nhat, dau_doan_thu_hai)
    o2 = tinh_huong_ba_diem(dau_doan_thu_nhat, cuoi_doan_thu_nhat, cuoi_doan_thu_hai)
    o3 = tinh_huong_ba_diem(dau_doan_thu_hai, cuoi_doan_thu_hai, dau_doan_thu_nhat)
    o4 = tinh_huong_ba_diem(dau_doan_thu_hai, cuoi_doan_thu_hai, cuoi_doan_thu_nhat)
    if ((o1 > EPSILON and o2 < -EPSILON) or (o1 < -EPSILON and o2 > EPSILON)) and (
        (o3 > EPSILON and o4 < -EPSILON) or (o3 < -EPSILON and o4 > EPSILON)
    ):
        return True
    return (
        (abs(o1) <= EPSILON and diem_nam_tren_doan(dau_doan_thu_nhat, dau_doan_thu_hai, cuoi_doan_thu_nhat))
        or (abs(o2) <= EPSILON and diem_nam_tren_doan(dau_doan_thu_nhat, cuoi_doan_thu_hai, cuoi_doan_thu_nhat))
        or (abs(o3) <= EPSILON and diem_nam_tren_doan(dau_doan_thu_hai, dau_doan_thu_nhat, cuoi_doan_thu_hai))
        or (abs(o4) <= EPSILON and diem_nam_tren_doan(dau_doan_thu_hai, cuoi_doan_thu_nhat, cuoi_doan_thu_hai))
    )


@dataclass(frozen=True)
class MatNaDatLien:
    """Các vòng Natural Earth và hộp bao dùng để kiểm tra nhanh."""

    cac_vong_da_giac: list[list[Diem]]
    cac_hop_bao: list[tuple[float, float, float, float]]

    @classmethod
    def doc_tu_shapefile(cls, duong_dan: Path | str = TEP_SHAPEFILE_MAC_DINH):
        duong_dan = Path(duong_dan)
        if not duong_dan.exists():
            raise FileNotFoundError(f"Land shapefile not found: {duong_dan}")
        cac_vong_da_giac = doc_cac_vong_da_giac(duong_dan)
        return cls(cac_vong_da_giac=cac_vong_da_giac, cac_hop_bao=[tao_hop_bao_vong(vong_da_giac) for vong_da_giac in cac_vong_da_giac])

    def chua_diem(self, diem: Diem):
        kinh_do, vi_do = diem
        so_vong_chua_diem = 0
        for vong_da_giac, hop_bao in zip(self.cac_vong_da_giac, self.cac_hop_bao):
            if hop_bao[0] <= kinh_do <= hop_bao[1] and hop_bao[2] <= vi_do <= hop_bao[3]:
                so_vong_chua_diem += int(diem_o_trong_vong(diem, vong_da_giac))
        return so_vong_chua_diem % 2 == 1

    def doan_cat_dat(self, diem_dau: Diem, diem_cuoi: Diem):
        # Điểm đầu, điểm giữa và điểm cuối giúp phát hiện đoạn nằm hoàn toàn trên đất.
        diem_giua = noi_suy_duong_tron_lon(diem_dau, diem_cuoi, 0.5)
        if self.chua_diem(diem_dau) or self.chua_diem(diem_giua) or self.chua_diem(diem_cuoi):
            return True

        hop_bao_doan = (
            min(diem_dau[0], diem_cuoi[0]),
            max(diem_dau[0], diem_cuoi[0]),
            min(diem_dau[1], diem_cuoi[1]),
            max(diem_dau[1], diem_cuoi[1]),
        )
        for vong_da_giac, hop_bao in zip(self.cac_vong_da_giac, self.cac_hop_bao):
            if not hai_hop_bao_giao_nhau(hop_bao_doan, hop_bao):
                continue
            cac_canh_vong_khep_kin = zip(vong_da_giac, vong_da_giac[1:] + vong_da_giac[:1])
            if any(hai_doan_giao_nhau(diem_dau, diem_cuoi, dau_canh, cuoi_canh) for dau_canh, cuoi_canh in cac_canh_vong_khep_kin):
                return True
        return False


def kiem_tra_tuyen_cat_dat(
    cac_diem_tuyen: Iterable[Diem],
    mat_na_dat: MatNaDatLien,
    khoang_cach_toi_da_nm: float = 5.0,
):
    """Kiểm tra từng đoạn nhỏ và trả về các đoạn gốc vi phạm."""
    cac_diem = list(cac_diem_tuyen)
    cac_doan_vi_pham: list[int] = []
    for index, (diem_dau, diem_cuoi) in enumerate(zip(cac_diem, cac_diem[1:]), start=1):
        cac_mau = chia_diem_tren_doan(diem_dau, diem_cuoi, khoang_cach_toi_da_nm)
        if any(
            mat_na_dat.doan_cat_dat(diem_thu_nhat, diem_thu_hai)
            for diem_thu_nhat, diem_thu_hai in zip(cac_mau, cac_mau[1:])
        ):
            cac_doan_vi_pham.append(index)
    return bool(cac_doan_vi_pham), cac_doan_vi_pham


def danh_gia_hinh_hoc_tuyen(
    tuyen: dict[str, Any], mat_na_dat: MatNaDatLien, khoang_cach_toi_da_nm: float = 5.0
):
    """Tính các chỉ số hình học ổn định cho một tuyến."""
    cac_diem_tuyen: list[Diem] = tuyen["waypoints"]
    cac_diem_mau = chia_diem_tren_tuyen(cac_diem_tuyen, khoang_cach_toi_da_nm)
    cac_khoang_cach_mau = [
        tinh_khoang_cach_trac_dia_nm(diem_dau, diem_cuoi)
        for diem_dau, diem_cuoi in zip(cac_diem_mau, cac_diem_mau[1:])
    ]
    cat_dat, cac_doan_vi_pham = kiem_tra_tuyen_cat_dat(
        cac_diem_tuyen, mat_na_dat, khoang_cach_toi_da_nm
    )
    return {
        "route_id": tuyen["route_id"],
        "name": tuyen["name"],
        "waypoint_count": len(cac_diem_tuyen),
        "segment_count": len(cac_diem_tuyen) - 1,
        "distance_nm": round(tinh_khoang_cach_tuyen_nm(cac_diem_tuyen), 6),
        "sample_count": len(cac_diem_mau),
        "maximum_sample_gap_nm": round(max(cac_khoang_cach_mau, default=0.0), 6),
        "spacing_limit_nm": khoang_cach_toi_da_nm,
        "spacing_valid": all(khoang_cach <= khoang_cach_toi_da_nm + 1e-9 for khoang_cach in cac_khoang_cach_mau),
        "crosses_land": cat_dat,
        "land_violating_segments": cac_doan_vi_pham,
    }


def doc_khoang_cach_cau_hinh(duong_dan: Path = TEP_KICH_BAN_MAC_DINH):
    kich_ban = yaml.safe_load(duong_dan.read_text(encoding="utf-8"))
    return float(kich_ban["route_sampling"]["maximum_spacing_nm"])


def tao_bao_cao(
    tep_tuyen: Path | str = TEP_TUYEN_MAC_DINH,
    tep_shapefile: Path | str = TEP_SHAPEFILE_MAC_DINH,
    khoang_cach_toi_da_nm: float | None = None,
):
    """Đánh giá mọi tuyến và trả về báo cáo có thể ghi thành JSON."""
    khoang_cach_mau = doc_khoang_cach_cau_hinh() if khoang_cach_toi_da_nm is None else khoang_cach_toi_da_nm
    cac_tuyen = doc_cac_tuyen(tep_tuyen)
    mat_na_dat = MatNaDatLien.doc_tu_shapefile(tep_shapefile)
    return {
        "coordinate_order": ["longitude", "latitude"],
        "distance_method": "Vincenty inverse on WGS84 ellipsoid",
        "distance_unit": "nautical_mile",
        "maximum_spacing_nm": khoang_cach_mau,
        "land_source": "Natural Earth Land 1:10m version 5.1.1",
        "usage_note": "Chỉ dùng để sàng lọc nghiên cứu; không phù hợp cho dẫn đường.",
        "routes": [
            danh_gia_hinh_hoc_tuyen(tuyen, mat_na_dat, khoang_cach_mau) for tuyen in cac_tuyen
        ],
    }


def main():
    # Cau hinh Terminal UTF-8 de hien thi tieng Viet co dau.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    bo_phan_tich = argparse.ArgumentParser(description=__doc__)
    bo_phan_tich.add_argument("--routes", type=Path, default=TEP_TUYEN_MAC_DINH)
    bo_phan_tich.add_argument("--land", type=Path, default=TEP_SHAPEFILE_MAC_DINH)
    bo_phan_tich.add_argument("--output", type=Path, default=TEP_KET_QUA_MAC_DINH)
    bo_phan_tich.add_argument("--maximum-spacing-nm", type=float, default=None)
    tham_so = bo_phan_tich.parse_args()

    bao_cao = tao_bao_cao(tham_so.routes, tham_so.land, tham_so.maximum_spacing_nm)
    tham_so.output.parent.mkdir(parents=True, exist_ok=True)
    tham_so.output.write_text(
        json.dumps(bao_cao, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(bao_cao, indent=2, ensure_ascii=False))
    print(f"Wrote {tham_so.output}")


if __name__ == "__main__":
    main()
