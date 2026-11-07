"""Tạo bảng kết quả ba tuyến STEP 2 từ báo cáo của evaluator."""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


THU_MUC_GOC = Path(__file__).resolve().parents[1]
TEP_DANH_GIA = THU_MUC_GOC / "outputs" / "evaluation_results.json"
THU_MUC_BANG = THU_MUC_GOC / "outputs" / "tables"
TEP_CSV = THU_MUC_BANG / "route_results.csv"
TEP_ANH = THU_MUC_BANG / "route_results.png"


def doc_bao_cao_danh_gia(duong_dan=TEP_DANH_GIA):
    """Đọc báo cáo evaluator và kiểm tra danh sách tuyến."""
    duong_dan = Path(duong_dan)
    if not duong_dan.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {duong_dan}; hãy chạy src/evaluator.py trước."
        )
    bao_cao = json.loads(duong_dan.read_text(encoding="utf-8"))
    if not isinstance(bao_cao.get("routes"), list) or not bao_cao["routes"]:
        raise ValueError("evaluation_results.json không chứa danh sách routes hợp lệ")
    return bao_cao


def ghep_ma_vi_pham(cac_vi_pham):
    """Ghép mã vi phạm duy nhất để bảng ngắn gọn nhưng vẫn truy vết được."""
    cac_ma = []
    for vi_pham in cac_vi_pham:
        ma = str(vi_pham.get("code", "UNKNOWN"))
        if ma not in cac_ma:
            cac_ma.append(ma)
    return "; ".join(cac_ma) if cac_ma else "Không"


def tao_bang_ket_qua(bao_cao):
    """Chuyển kết quả evaluator thành bảng tóm tắt, không suy diễn tiết kiệm."""
    cac_dong = []
    for tuyen in bao_cao["routes"]:
        vi_pham = tuyen.get("violations", {})
        vi_pham_cung = vi_pham.get("hard", [])
        vi_pham_mem = vi_pham.get("soft", [])
        kha_thi = bool(tuyen.get("feasible", False))
        cac_dong.append(
            {
                "route_id": tuyen.get("route_id"),
                "route_name": tuyen.get("route_name"),
                "distance_nm": tuyen.get("distance_nm"),
                "duration_h": tuyen.get("duration_h"),
                "estimated_fuel_t": tuyen.get("fuel_t"),
                "estimated_co2_t": tuyen.get("co2_t"),
                "feasible": kha_thi,
                "hard_violation_count": len(vi_pham_cung),
                "soft_violation_count": len(vi_pham_mem),
                "violation_codes": ghep_ma_vi_pham(vi_pham_cung + vi_pham_mem),
                "fitness": tuyen.get("fitness") if kha_thi else None,
                "result_note": (
                    "Tuyến thử khả thi; chưa phải tuyến tối ưu."
                    if kha_thi
                    else "Tuyến thử không khả thi; không dùng để so sánh lợi ích."
                ),
            }
        )
    return pd.DataFrame(cac_dong)


def dinh_dang_so(gia_tri):
    """Định dạng số cho ảnh bảng và giữ dấu gạch ngang với giá trị thiếu."""
    if gia_tri is None or pd.isna(gia_tri):
        return "—"
    return f"{float(gia_tri):.3f}"


def ve_bang_ket_qua(bang, duong_dan=TEP_ANH):
    """Vẽ bảng PNG để chèn vào báo cáo hoặc dùng làm ảnh minh chứng."""
    duong_dan = Path(duong_dan)
    tieu_de_cot = [
        "Tuyến",
        "Khoảng cách\n(NM)",
        "Thời gian\n(giờ)",
        "Nhiên liệu\nước tính (t)",
        "CO₂ ước tính\n(t)",
        "Khả thi",
        "Vi phạm",
        "Fitness",
    ]
    cac_o = []
    for _, dong in bang.iterrows():
        cac_o.append(
            [
                dong["route_id"],
                dinh_dang_so(dong["distance_nm"]),
                dinh_dang_so(dong["duration_h"]),
                dinh_dang_so(dong["estimated_fuel_t"]),
                dinh_dang_so(dong["estimated_co2_t"]),
                "Có" if dong["feasible"] else "Không",
                dong["violation_codes"],
                dinh_dang_so(dong["fitness"]),
            ]
        )

    hinh, truc = plt.subplots(figsize=(15.5, 4.8))
    truc.axis("off")
    truc.set_title(
        "Bảng kết quả đánh giá ba tuyến thủ công – GreenShip STEP 2",
        fontsize=16,
        fontweight="bold",
        pad=20,
    )
    bang_anh = truc.table(
        cellText=cac_o,
        colLabels=tieu_de_cot,
        cellLoc="center",
        colLoc="center",
        loc="center",
        colWidths=[0.06, 0.10, 0.10, 0.12, 0.12, 0.08, 0.30, 0.09],
    )
    bang_anh.auto_set_font_size(False)
    bang_anh.set_fontsize(10)
    bang_anh.scale(1.0, 2.2)

    for (hang, cot), o in bang_anh.get_celld().items():
        o.set_edgecolor("#78909c")
        if hang == 0:
            o.set_facecolor("#1565c0")
            o.set_text_props(color="white", fontweight="bold")
        else:
            kha_thi = bool(bang.iloc[hang - 1]["feasible"])
            o.set_facecolor("#e8f5e9" if kha_thi else "#ffebee")
            if cot == 5:
                o.set_text_props(
                    color="#1b5e20" if kha_thi else "#b71c1c",
                    fontweight="bold",
                )

    hinh.text(
        0.5,
        0.055,
        "Các giá trị nhiên liệu và CO₂ là ước tính của mô hình thử nghiệm. "
        "Các tuyến chưa qua tối ưu; không khẳng định mức tiết kiệm.",
        ha="center",
        fontsize=10,
        color="#37474f",
    )
    hinh.text(
        0.5,
        0.015,
        "R01: tuyến tham chiếu thủ công khả thi · R02: tuyến cố ý cắt đất · "
        "R03: tuyến thay thế ngoài khơi",
        ha="center",
        fontsize=9,
        color="#546e7a",
    )
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    hinh.savefig(duong_dan, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(hinh)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    bao_cao = doc_bao_cao_danh_gia()
    bang = tao_bang_ket_qua(bao_cao)
    THU_MUC_BANG.mkdir(parents=True, exist_ok=True)
    bang.to_csv(TEP_CSV, index=False, encoding="utf-8-sig")
    ve_bang_ket_qua(bang, TEP_ANH)
    print(bang.to_string(index=False))
    print(f"Đã ghi bảng CSV: {TEP_CSV}")
    print(f"Đã tạo ảnh bảng: {TEP_ANH}")


if __name__ == "__main__":
    main()
