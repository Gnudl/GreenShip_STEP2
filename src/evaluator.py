"""Đánh giá thống nhất một tuyến GreenShip STEP 2.

Mô hình tối thiểu giữ công suất, SFOC và tốc độ qua nước không đổi.
Dòng chảy dọc tuyến chỉ được cộng vào SOG khi cả ``uo`` và ``vo`` hợp lệ.
Gió và sóng được tra cứu để kiểm tra dữ liệu/ràng buộc, chưa dùng để hiệu
chỉnh tốc độ hoặc công suất vì chưa có mô hình tàu đã hiệu chuẩn.
"""

import json
import math
import sys
from copy import deepcopy
from pathlib import Path

import pandas as pd
import yaml

from constraints import kiem_tra_rang_buoc, tao_vi_pham
from route_geometry import (
    MatNaDatLien,
    chia_diem_tren_doan,
    danh_gia_hinh_hoc_tuyen,
    doc_cac_tuyen,
    tinh_khoang_cach_trac_dia_nm,
    tinh_khoang_cach_tuyen_nm,
)
from weather import KhoDuLieuThoiTiet, dinh_dang_utc, doi_sang_thoi_diem_utc


THU_MUC_GOC = Path(__file__).resolve().parents[1]
TEP_KICH_BAN = THU_MUC_GOC / "config" / "scenario.yaml"
TEP_TAU = THU_MUC_GOC / "config" / "ship.json"
TEP_TUYEN = THU_MUC_GOC / "data" / "routes" / "manual_routes.json"
TEP_SHAPEFILE = THU_MUC_GOC / "data" / "land" / "ne_10m_land" / "ne_10m_land.shp"
THU_MUC_DA_XU_LY = THU_MUC_GOC / "data" / "processed"
TEP_KET_QUA = THU_MUC_GOC / "outputs" / "evaluation_results.json"

SO_HAI_LY_MOI_MET_GIAY = 1.9438444924406


def tao_vi_pham_dau_vao(thong_bao, chi_tiet):
    """Tạo hard violation cho cấu hình hoặc phép tính không hợp lệ."""
    return tao_vi_pham("INPUT_INVALID", "hard", thong_bao, chi_tiet, 1.0)


def lay_gia_tri_tham_so(cau_hinh_tau, ten, don_vi, cho_phep_bang_khong=False):
    """Đọc một tham số tàu, đồng thời kiểm tra đơn vị và miền giá trị."""
    muc = cau_hinh_tau.get("parameters", {}).get(ten)
    if not isinstance(muc, dict) or "value" not in muc:
        raise ValueError(f"Thiếu tham số tàu: {ten}")
    if muc.get("unit") != don_vi:
        raise ValueError(
            f"Đơn vị của {ten} phải là {don_vi}, nhận được {muc.get('unit')!r}"
        )
    gia_tri = float(muc["value"])
    hop_le = gia_tri >= 0.0 if cho_phep_bang_khong else gia_tri > 0.0
    if not math.isfinite(gia_tri) or not hop_le:
        dau = ">=" if cho_phep_bang_khong else ">"
        raise ValueError(f"{ten} phải {dau} 0 và là số hữu hạn")
    return gia_tri


def doc_tham_so_tau(cau_hinh_tau):
    """Trả các tham số đã kiểm tra của mô hình tàu tối thiểu."""
    return {
        "speed_through_water_kn": lay_gia_tri_tham_so(
            cau_hinh_tau, "speed_through_water_kn", "kn"
        ),
        "service_power_kw": lay_gia_tri_tham_so(
            cau_hinh_tau, "service_power_kw", "kW", cho_phep_bang_khong=True
        ),
        "sfoc_g_per_kwh": lay_gia_tri_tham_so(
            cau_hinh_tau, "sfoc_g_per_kwh", "g/kWh"
        ),
        "co2_emission_factor_t_per_t_fuel": lay_gia_tri_tham_so(
            cau_hinh_tau,
            "co2_emission_factor_t_per_t_fuel",
            "tCO2/t-fuel",
        ),
        "fuel_type": str(
            cau_hinh_tau.get("parameters", {})
            .get("fuel_type", {})
            .get("value", "UNKNOWN")
        ),
    }


def tinh_nhien_lieu_tan(cong_suat_kw, sfoc_g_kwh, thoi_gian_h):
    """Tính nhiên liệu tấn từ kW × g/kWh × giờ, có kiểm tra đầu vào."""
    cac_gia_tri = (float(cong_suat_kw), float(sfoc_g_kwh), float(thoi_gian_h))
    if not all(math.isfinite(gia_tri) for gia_tri in cac_gia_tri):
        raise ValueError("Các đại lượng tính nhiên liệu phải là số hữu hạn")
    if cac_gia_tri[0] < 0.0 or cac_gia_tri[1] <= 0.0 or cac_gia_tri[2] < 0.0:
        raise ValueError("Power >= 0, SFOC > 0 và thời gian >= 0")
    return cac_gia_tri[0] * cac_gia_tri[1] * cac_gia_tri[2] / 1_000_000.0


def tinh_co2_tan(nhien_lieu_tan, he_so_phat_thai):
    """Tính estimated tank-to-wake CO2 theo tCO2/t nhiên liệu."""
    nhien_lieu_tan = float(nhien_lieu_tan)
    he_so_phat_thai = float(he_so_phat_thai)
    if not math.isfinite(nhien_lieu_tan) or not math.isfinite(he_so_phat_thai):
        raise ValueError("Nhiên liệu và hệ số phát thải phải là số hữu hạn")
    if nhien_lieu_tan < 0.0 or he_so_phat_thai <= 0.0:
        raise ValueError("Nhiên liệu >= 0 và hệ số phát thải > 0")
    return nhien_lieu_tan * he_so_phat_thai


def tinh_huong_don_vi(diem_dau, diem_cuoi):
    """Trả thành phần đơn vị hướng đông và hướng bắc của đoạn tuyến."""
    kinh_do_1, vi_do_1 = map(math.radians, diem_dau)
    kinh_do_2, vi_do_2 = map(math.radians, diem_cuoi)
    chenh_kinh_do = kinh_do_2 - kinh_do_1
    thanh_phan_dong = math.sin(chenh_kinh_do) * math.cos(vi_do_2)
    thanh_phan_bac = (
        math.cos(vi_do_1) * math.sin(vi_do_2)
        - math.sin(vi_do_1) * math.cos(vi_do_2) * math.cos(chenh_kinh_do)
    )
    do_lon = math.hypot(thanh_phan_dong, thanh_phan_bac)
    if do_lon <= 1e-15:
        return 0.0, 0.0
    return thanh_phan_dong / do_lon, thanh_phan_bac / do_lon


def tinh_dong_chay_doc_tuyen_kn(mau_thoi_tiet, diem_dau, diem_cuoi):
    """Chiếu dòng chảy đông/bắc lên hướng đi; trả None nếu dòng chảy thiếu."""
    dong_chay_dong = mau_thoi_tiet.get("current_u_mps")
    dong_chay_bac = mau_thoi_tiet.get("current_v_mps")
    if dong_chay_dong is None or dong_chay_bac is None:
        return None
    huong_dong, huong_bac = tinh_huong_don_vi(diem_dau, diem_cuoi)
    return (
        float(dong_chay_dong) * huong_dong
        + float(dong_chay_bac) * huong_bac
    ) * SO_HAI_LY_MOI_MET_GIAY


def goi_tra_cuu_thoi_tiet(nguon_thoi_tiet, vi_do, kinh_do, thoi_gian_utc):
    """Gọi nguồn thời tiết dạng đối tượng hoặc callable để tiện kiểm thử."""
    if hasattr(nguon_thoi_tiet, "weather_at"):
        return nguon_thoi_tiet.weather_at(vi_do, kinh_do, thoi_gian_utc)
    if callable(nguon_thoi_tiet):
        return nguon_thoi_tiet(vi_do, kinh_do, thoi_gian_utc)
    raise TypeError("weather phải là callable hoặc có phương thức weather_at")


def tao_ket_qua_loi_dau_vao(tuyen, thong_bao, chi_tiet=None):
    """Trả từ điển kết quả chuẩn khi chưa thể thực hiện phép tính."""
    vi_pham = tao_vi_pham_dau_vao(thong_bao, chi_tiet or {})
    return {
        "route_id": tuyen.get("route_id", "UNKNOWN") if isinstance(tuyen, dict) else "UNKNOWN",
        "model_status": "toy_model_estimate",
        "feasible": False,
        "violations": {"hard": [vi_pham], "soft": []},
        "hard_violation_count": 1,
        "soft_violation_count": 0,
        "total_normalized_violation": 1.0,
        "distance_nm": None,
        "duration_h": None,
        "fuel_t": None,
        "co2_t": None,
        "fitness": None,
        "segments": [],
    }


def evaluate_route(route, departure_utc, ship, weather, land, cfg):
    """Đánh giá một tuyến bằng cùng quy trình hình học–thời tiết–nhiên liệu.

    API tiếng Anh này được giữ ổn định theo hợp đồng STEP 2. Các hàm hỗ trợ
    nội bộ dùng tên tiếng Việt. Hàm không dùng số ngẫu nhiên và không đọc tệp.
    """
    try:
        tham_so_tau = doc_tham_so_tau(ship)
        thoi_diem_hien_tai = doi_sang_thoi_diem_utc(departure_utc)
        if not isinstance(route, dict) or len(route.get("waypoints", [])) < 2:
            raise ValueError("Tuyến phải có ít nhất hai waypoint")
        if not hasattr(land, "doan_cat_dat"):
            raise TypeError("land phải là mặt nạ đất có phương thức doan_cat_dat")
        khoang_cach_mau_nm = float(cfg["route_sampling"]["maximum_spacing_nm"])
        if khoang_cach_mau_nm <= 0.0:
            raise ValueError("maximum_spacing_nm phải lớn hơn 0")
        cau_hinh_rang_buoc = cfg["constraints"]
    except Exception as loi:
        return tao_ket_qua_loi_dau_vao(route, str(loi))

    thong_tin_hinh_hoc = danh_gia_hinh_hoc_tuyen(
        route, land, khoang_cach_mau_nm
    )
    cac_diem_tuyen = route["waypoints"]
    cac_mau_thoi_tiet = []
    cac_doan_ket_qua = []
    cac_vi_pham_van_hanh = []
    tong_thoi_gian_h = 0.0
    tong_nhien_lieu_tan = 0.0
    khong_tinh_duoc = False

    for chi_so_doan, (diem_dau, diem_cuoi) in enumerate(
        zip(cac_diem_tuyen, cac_diem_tuyen[1:]), start=1
    ):
        cac_diem_mau = chia_diem_tren_doan(
            tuple(diem_dau), tuple(diem_cuoi), khoang_cach_mau_nm
        )
        thoi_diem_khoi_hanh_doan = thoi_diem_hien_tai
        thoi_gian_doan_h = 0.0
        nhien_lieu_doan_tan = 0.0
        cac_khoang_mau = []

        for chi_so_mau, (mau_dau, mau_cuoi) in enumerate(
            zip(cac_diem_mau, cac_diem_mau[1:]), start=1
        ):
            khoang_cach_nm = tinh_khoang_cach_trac_dia_nm(mau_dau, mau_cuoi)
            ket_qua_thoi_tiet = goi_tra_cuu_thoi_tiet(
                weather,
                mau_dau[1],
                mau_dau[0],
                thoi_diem_hien_tai,
            )
            cac_mau_thoi_tiet.append(ket_qua_thoi_tiet)
            dong_chay_doc_tuyen_kn = tinh_dong_chay_doc_tuyen_kn(
                ket_qua_thoi_tiet, mau_dau, mau_cuoi
            )
            toc_do_qua_dat_kn = tham_so_tau["speed_through_water_kn"]
            if dong_chay_doc_tuyen_kn is not None:
                toc_do_qua_dat_kn += dong_chay_doc_tuyen_kn

            if not math.isfinite(toc_do_qua_dat_kn) or toc_do_qua_dat_kn <= 0.0:
                cac_vi_pham_van_hanh.append(
                    tao_vi_pham(
                        "NON_POSITIVE_SOG",
                        "hard",
                        "Tốc độ qua đất không dương nên không thể tính thời gian.",
                        {
                            "segment_index": chi_so_doan,
                            "sample_interval_index": chi_so_mau,
                            "speed_through_water_kn": tham_so_tau[
                                "speed_through_water_kn"
                            ],
                            "current_along_route_kn": dong_chay_doc_tuyen_kn,
                            "speed_over_ground_kn": toc_do_qua_dat_kn,
                        },
                        1.0,
                    )
                )
                khong_tinh_duoc = True
                break

            thoi_gian_mau_h = khoang_cach_nm / toc_do_qua_dat_kn
            nhien_lieu_mau_tan = tinh_nhien_lieu_tan(
                tham_so_tau["service_power_kw"],
                tham_so_tau["sfoc_g_per_kwh"],
                thoi_gian_mau_h,
            )
            thoi_diem_den_mau = thoi_diem_hien_tai + pd.Timedelta(
                hours=thoi_gian_mau_h
            )
            cac_khoang_mau.append(
                {
                    "sample_interval_index": chi_so_mau,
                    "start": [round(mau_dau[0], 8), round(mau_dau[1], 8)],
                    "end": [round(mau_cuoi[0], 8), round(mau_cuoi[1], 8)],
                    "departure_utc": dinh_dang_utc(thoi_diem_hien_tai),
                    "arrival_utc": dinh_dang_utc(thoi_diem_den_mau),
                    "distance_nm": round(khoang_cach_nm, 6),
                    "speed_through_water_kn": tham_so_tau[
                        "speed_through_water_kn"
                    ],
                    "current_along_route_kn": (
                        None
                        if dong_chay_doc_tuyen_kn is None
                        else round(dong_chay_doc_tuyen_kn, 6)
                    ),
                    "current_applied": dong_chay_doc_tuyen_kn is not None,
                    "speed_over_ground_kn": round(toc_do_qua_dat_kn, 6),
                    "duration_h": round(thoi_gian_mau_h, 9),
                    "fuel_t": round(nhien_lieu_mau_tan, 9),
                    "weather": ket_qua_thoi_tiet,
                }
            )
            thoi_gian_doan_h += thoi_gian_mau_h
            nhien_lieu_doan_tan += nhien_lieu_mau_tan
            thoi_diem_hien_tai = thoi_diem_den_mau

        khoang_cach_doan_nm = tinh_khoang_cach_trac_dia_nm(
            tuple(diem_dau), tuple(diem_cuoi)
        )
        cac_doan_ket_qua.append(
            {
                "segment_index": chi_so_doan,
                "start": list(diem_dau),
                "end": list(diem_cuoi),
                "departure_utc": dinh_dang_utc(thoi_diem_khoi_hanh_doan),
                "arrival_utc": (
                    None if khong_tinh_duoc else dinh_dang_utc(thoi_diem_hien_tai)
                ),
                "distance_nm": round(khoang_cach_doan_nm, 6),
                "duration_h": None if khong_tinh_duoc else round(thoi_gian_doan_h, 9),
                "fuel_t": None if khong_tinh_duoc else round(nhien_lieu_doan_tan, 9),
                "sample_interval_count": len(cac_khoang_mau),
                "sample_intervals": cac_khoang_mau,
            }
        )
        if khong_tinh_duoc:
            break
        tong_thoi_gian_h += thoi_gian_doan_h
        tong_nhien_lieu_tan += nhien_lieu_doan_tan

    khoang_cach_tham_chieu_nm = cfg.get("reference_distance_nm")
    ket_qua_rang_buoc = kiem_tra_rang_buoc(
        thong_tin_hinh_hoc,
        cac_diem_tuyen,
        cau_hinh_rang_buoc,
        khoang_cach_tham_chieu_nm=khoang_cach_tham_chieu_nm,
        cac_mau_thoi_tiet=cac_mau_thoi_tiet,
    )
    if cac_vi_pham_van_hanh:
        ket_qua_rang_buoc["violations"]["hard"].extend(cac_vi_pham_van_hanh)
        ket_qua_rang_buoc["hard_violation_count"] += len(cac_vi_pham_van_hanh)
        ket_qua_rang_buoc["total_normalized_violation"] = round(
            ket_qua_rang_buoc["total_normalized_violation"]
            + sum(muc["normalized_severity"] for muc in cac_vi_pham_van_hanh),
            6,
        )
        ket_qua_rang_buoc["feasible"] = False

    if khong_tinh_duoc:
        tong_thoi_gian_h = None
        tong_nhien_lieu_tan = None
        tong_co2_tan = None
    else:
        tong_co2_tan = tinh_co2_tan(
            tong_nhien_lieu_tan,
            tham_so_tau["co2_emission_factor_t_per_t_fuel"],
        )

    kha_thi = ket_qua_rang_buoc["feasible"]
    # Fuel là mục tiêu chính; không cộng CO2 vì hai đại lượng tỷ lệ thuận khi CF cố định.
    diem_danh_gia = tong_nhien_lieu_tan if kha_thi and not khong_tinh_duoc else None
    return {
        "route_id": route.get("route_id", "UNKNOWN"),
        "route_name": route.get("name", "Không có tên"),
        "model_status": "toy_model_estimate",
        "departure_utc": dinh_dang_utc(departure_utc),
        "arrival_utc": None if khong_tinh_duoc else dinh_dang_utc(thoi_diem_hien_tai),
        "feasible": kha_thi,
        "violations": ket_qua_rang_buoc["violations"],
        "hard_violation_count": ket_qua_rang_buoc["hard_violation_count"],
        "soft_violation_count": ket_qua_rang_buoc["soft_violation_count"],
        "total_normalized_violation": ket_qua_rang_buoc[
            "total_normalized_violation"
        ],
        "distance_nm": round(float(thong_tin_hinh_hoc["distance_nm"]), 6),
        "duration_h": None if tong_thoi_gian_h is None else round(tong_thoi_gian_h, 6),
        "fuel_t": None if tong_nhien_lieu_tan is None else round(tong_nhien_lieu_tan, 6),
        "co2_t": None if tong_co2_tan is None else round(tong_co2_tan, 6),
        "fitness": None if diem_danh_gia is None else round(diem_danh_gia, 6),
        "fitness_definition": "fuel_t; chỉ tính cho tuyến feasible",
        "ship_model": {
            "fuel_type": tham_so_tau["fuel_type"],
            "speed_through_water_kn": tham_so_tau["speed_through_water_kn"],
            "service_power_kw": tham_so_tau["service_power_kw"],
            "sfoc_g_per_kwh": tham_so_tau["sfoc_g_per_kwh"],
            "co2_emission_factor_t_per_t_fuel": tham_so_tau[
                "co2_emission_factor_t_per_t_fuel"
            ],
        },
        "operating_assumptions": {
            "constant_power_and_sfoc": True,
            "weather_speed_correction_enabled": False,
            "valid_current_projection_enabled": True,
            "missing_current_fallback": "Giữ SOG bằng STW; dòng chảy là dữ liệu tùy chọn.",
            "co2_scope": "estimated tank-to-wake CO2",
        },
        "geometry": thong_tin_hinh_hoc,
        "segments": cac_doan_ket_qua,
    }


def tao_bao_cao_danh_gia():
    """Đọc dữ liệu dự án và đánh giá ba tuyến bằng cùng evaluate_route()."""
    kich_ban = yaml.safe_load(TEP_KICH_BAN.read_text(encoding="utf-8"))
    cau_hinh_tau = json.loads(TEP_TAU.read_text(encoding="utf-8"))
    cac_tuyen = doc_cac_tuyen(TEP_TUYEN)
    ma_tuyen_tham_chieu = kich_ban["constraints"]["detour"]["reference_route_id"]
    tuyen_tham_chieu = next(
        tuyen for tuyen in cac_tuyen if tuyen["route_id"] == ma_tuyen_tham_chieu
    )
    cau_hinh_danh_gia = deepcopy(kich_ban)
    cau_hinh_danh_gia["reference_distance_nm"] = tinh_khoang_cach_tuyen_nm(
        tuyen_tham_chieu["waypoints"]
    )
    mat_na_dat = MatNaDatLien.doc_tu_shapefile(TEP_SHAPEFILE)

    with KhoDuLieuThoiTiet(THU_MUC_DA_XU_LY) as kho_thoi_tiet:
        cac_ket_qua = [
            evaluate_route(
                tuyen,
                kich_ban["departure_utc"],
                cau_hinh_tau,
                kho_thoi_tiet,
                mat_na_dat,
                cau_hinh_danh_gia,
            )
            for tuyen in cac_tuyen
        ]

    return {
        "scenario_id": kich_ban["scenario_id"],
        "result_label": "Ước tính mô hình STEP 2; không phải số liệu vận hành thực tế.",
        "evaluator": "evaluate_route() dùng chung cho mọi tuyến",
        "fitness_definition": "fuel_t cho tuyến feasible; tuyến infeasible có fitness=None",
        "baseline": {
            "route_id": ma_tuyen_tham_chieu,
            "definition": "Tuyến tham chiếu thủ công khả thi; không gọi Rhumb Line là ngắn nhất.",
        },
        "routes": cac_ket_qua,
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    bao_cao = tao_bao_cao_danh_gia()
    TEP_KET_QUA.parent.mkdir(parents=True, exist_ok=True)
    TEP_KET_QUA.write_text(
        json.dumps(bao_cao, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    bang_tom_tat = [
        {
            "route_id": muc["route_id"],
            "distance_nm": muc["distance_nm"],
            "duration_h": muc["duration_h"],
            "fuel_t": muc["fuel_t"],
            "co2_t": muc["co2_t"],
            "feasible": muc["feasible"],
            "fitness": muc["fitness"],
            "hard_violations": muc["hard_violation_count"],
            "soft_violations": muc["soft_violation_count"],
        }
        for muc in bao_cao["routes"]
    ]
    print(json.dumps(bang_tom_tat, indent=2, ensure_ascii=False))
    print(f"Đã ghi báo cáo đầy đủ: {TEP_KET_QUA}")


if __name__ == "__main__":
    main()
