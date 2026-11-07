"""Phân loại hard/soft constraints và trả danh sách vi phạm của từng tuyến."""

import json
import sys
from pathlib import Path

import yaml

from route_geometry import doc_cac_tuyen, tinh_khoang_cach_trac_dia_nm


THU_MUC_GOC = Path(__file__).resolve().parents[1]
TEP_KICH_BAN = THU_MUC_GOC / "config" / "scenario.yaml"
TEP_HINH_HOC = THU_MUC_GOC / "outputs" / "route_geometry.json"
TEP_KET_QUA = THU_MUC_GOC / "outputs" / "constraints_report.json"


def tao_vi_pham(ma, phan_loai, thong_bao, chi_tiet, muc_do_chuan_hoa):
    """Tạo một bản ghi vi phạm có cấu trúc thống nhất."""
    return {
        "code": ma,
        "classification": phan_loai,
        "message": thong_bao,
        "details": chi_tiet,
        "normalized_severity": round(min(1.0, max(0.0, muc_do_chuan_hoa)), 6),
    }


def tim_doan_gan_bang_khong(cac_diem_tuyen, nguong_nm):
    """Trả về các đoạn lặp hoặc có chiều dài gần bằng không."""
    cac_doan = []
    for chi_so, (diem_dau, diem_cuoi) in enumerate(
        zip(cac_diem_tuyen, cac_diem_tuyen[1:]), start=1
    ):
        khoang_cach_nm = tinh_khoang_cach_trac_dia_nm(diem_dau, diem_cuoi)
        if khoang_cach_nm <= nguong_nm:
            cac_doan.append(
                {
                    "segment_index": chi_so,
                    "distance_nm": round(khoang_cach_nm, 9),
                    "start": list(diem_dau),
                    "end": list(diem_cuoi),
                }
            )
    return cac_doan


def kiem_tra_mau_thoi_tiet(cac_mau_thoi_tiet, cau_hinh_song):
    """Kiểm tra dữ liệu bắt buộc và ngưỡng sóng trên các mẫu thời tiết."""
    vi_pham_cung = []
    vi_pham_mem = []
    nguong_song_m = float(cau_hinh_song["swh_threshold_m"])
    phan_loai_song = cau_hinh_song.get("classification", "soft")

    for chi_so, mau in enumerate(cac_mau_thoi_tiet, start=1):
        if not mau.get("valid", False):
            vi_pham_cung.append(
                tao_vi_pham(
                    "MANDATORY_WEATHER_INVALID",
                    "hard",
                    "Thiếu dữ liệu thời tiết bắt buộc hoặc truy vấn nằm ngoài phạm vi.",
                    {
                        "sample_index": chi_so,
                        "query": mau.get("query"),
                        "note": mau.get("note", "không có chẩn đoán"),
                    },
                    1.0,
                )
            )
            continue

        do_cao_song_m = mau.get("wave_hs_m")
        if do_cao_song_m is not None and float(do_cao_song_m) > nguong_song_m:
            do_vuot_m = float(do_cao_song_m) - nguong_song_m
            vi_pham = tao_vi_pham(
                "WAVE_HEIGHT_EXCEEDED",
                phan_loai_song,
                "Độ cao sóng có nghĩa vượt ngưỡng giả định của nhóm.",
                {
                    "sample_index": chi_so,
                    "wave_hs_m": float(do_cao_song_m),
                    "threshold_m": nguong_song_m,
                    "exceedance_m": round(do_vuot_m, 6),
                    "query": mau.get("query"),
                },
                do_vuot_m / nguong_song_m,
            )
            if phan_loai_song == "hard":
                vi_pham_cung.append(vi_pham)
            else:
                vi_pham_mem.append(vi_pham)

    return vi_pham_cung, vi_pham_mem


def kiem_tra_rang_buoc(
    thong_tin_hinh_hoc,
    cac_diem_tuyen,
    cau_hinh,
    khoang_cach_tham_chieu_nm=None,
    cac_mau_thoi_tiet=None,
):
    """Đánh giá hard/soft constraints và trả feasible cùng violations."""
    vi_pham_cung = []
    vi_pham_mem = []

    if thong_tin_hinh_hoc.get("crosses_land", False):
        vi_pham_cung.append(
            tao_vi_pham(
                "LAND_CROSSING",
                "hard",
                "Tuyến cắt polygon đất liền và không khả thi.",
                {
                    "segment_indices": thong_tin_hinh_hoc.get(
                        "land_violating_segments", []
                    )
                },
                1.0,
            )
        )

    if not thong_tin_hinh_hoc.get("spacing_valid", False):
        vi_pham_cung.append(
            tao_vi_pham(
                "SAMPLING_SPACING_INVALID",
                "hard",
                "Khoảng cách giữa hai điểm mẫu vượt giới hạn cấu hình.",
                {
                    "maximum_sample_gap_nm": thong_tin_hinh_hoc.get(
                        "maximum_sample_gap_nm"
                    ),
                    "spacing_limit_nm": thong_tin_hinh_hoc.get("spacing_limit_nm"),
                },
                1.0,
            )
        )

    nguong_doan_nm = float(cau_hinh["near_zero_segment_nm"])
    cac_doan_gan_khong = tim_doan_gan_bang_khong(cac_diem_tuyen, nguong_doan_nm)
    if cac_doan_gan_khong:
        vi_pham_cung.append(
            tao_vi_pham(
                "NEAR_ZERO_SEGMENT",
                "hard",
                "Tuyến có waypoint lặp hoặc đoạn gần bằng không.",
                {
                    "threshold_nm": nguong_doan_nm,
                    "segments": cac_doan_gan_khong,
                },
                1.0,
            )
        )

    cau_hinh_duong_vong = cau_hinh["detour"]
    khoang_cach_nm = float(thong_tin_hinh_hoc["distance_nm"])
    if khoang_cach_tham_chieu_nm:
        ty_so = khoang_cach_nm / float(khoang_cach_tham_chieu_nm)
        nguong_ty_so = float(cau_hinh_duong_vong["ratio_threshold"])
        if ty_so > nguong_ty_so:
            do_vuot = ty_so - nguong_ty_so
            trong_so = float(cau_hinh_duong_vong.get("penalty_weight", 1.0))
            vi_pham_mem.append(
                tao_vi_pham(
                    "EXCESSIVE_DETOUR",
                    "soft",
                    "Tuyến dài hơn ngưỡng so với tuyến tham chiếu khả thi.",
                    {
                        "distance_nm": khoang_cach_nm,
                        "reference_distance_nm": float(khoang_cach_tham_chieu_nm),
                        "distance_ratio": round(ty_so, 6),
                        "ratio_threshold": nguong_ty_so,
                        "penalty_weight": trong_so,
                    },
                    do_vuot * trong_so,
                )
            )

    da_kiem_tra_thoi_tiet = cac_mau_thoi_tiet is not None
    if da_kiem_tra_thoi_tiet:
        cung_thoi_tiet, mem_thoi_tiet = kiem_tra_mau_thoi_tiet(
            cac_mau_thoi_tiet, cau_hinh["wave"]
        )
        vi_pham_cung.extend(cung_thoi_tiet)
        vi_pham_mem.extend(mem_thoi_tiet)

    tong_muc_vi_pham = sum(
        vi_pham["normalized_severity"]
        for vi_pham in vi_pham_cung + vi_pham_mem
    )
    return {
        "feasible": len(vi_pham_cung) == 0,
        "weather_checked": da_kiem_tra_thoi_tiet,
        "violations": {
            "hard": vi_pham_cung,
            "soft": vi_pham_mem,
        },
        "hard_violation_count": len(vi_pham_cung),
        "soft_violation_count": len(vi_pham_mem),
        "total_normalized_violation": round(tong_muc_vi_pham, 6),
    }


def tao_bao_cao_rang_buoc():
    """Áp dụng constraints hình học hiện có cho ba tuyến thủ công."""
    if not TEP_HINH_HOC.exists():
        raise FileNotFoundError(
            "Không tìm thấy outputs/route_geometry.json; hãy chạy src/route_geometry.py trước."
        )

    kich_ban = yaml.safe_load(TEP_KICH_BAN.read_text(encoding="utf-8"))
    cau_hinh = kich_ban["constraints"]
    cac_tuyen = {tuyen["route_id"]: tuyen for tuyen in doc_cac_tuyen()}
    du_lieu_hinh_hoc = json.loads(TEP_HINH_HOC.read_text(encoding="utf-8"))
    cac_hinh_hoc = {
        muc["route_id"]: muc for muc in du_lieu_hinh_hoc["routes"]
    }

    ma_tuyen_tham_chieu = cau_hinh["detour"]["reference_route_id"]
    khoang_cach_tham_chieu_nm = cac_hinh_hoc[ma_tuyen_tham_chieu]["distance_nm"]
    cac_ket_qua = []
    for ma_tuyen in ("R01", "R02", "R03"):
        ket_qua = kiem_tra_rang_buoc(
            cac_hinh_hoc[ma_tuyen],
            cac_tuyen[ma_tuyen]["waypoints"],
            cau_hinh,
            khoang_cach_tham_chieu_nm,
        )
        cac_ket_qua.append(
            {
                "route_id": ma_tuyen,
                "reference_route_id": ma_tuyen_tham_chieu,
                **ket_qua,
            }
        )

    return {
        "constraint_policy": {
            "land_crossing": "hard",
            "mandatory_weather_invalid": "hard",
            "near_zero_segment": "hard",
            "wave_height_exceeded": cau_hinh["wave"]["classification"],
            "excessive_detour": cau_hinh["detour"]["classification"],
        },
        "thresholds": cau_hinh,
        "weather_note": (
            "Báo cáo này mới kiểm tra hình học và đường vòng; thời tiết sẽ được "
            "kiểm tra khi evaluator truyền các mẫu weather_at()."
        ),
        "routes": cac_ket_qua,
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    bao_cao = tao_bao_cao_rang_buoc()
    TEP_KET_QUA.parent.mkdir(parents=True, exist_ok=True)
    TEP_KET_QUA.write_text(
        json.dumps(bao_cao, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(bao_cao, indent=2, ensure_ascii=False))
    print(f"Đã ghi báo cáo: {TEP_KET_QUA}")


if __name__ == "__main__":
    main()
