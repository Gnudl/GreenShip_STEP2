"""Chạy các truy vấn thời tiết STEP 2 có thể lặp lại và lưu kết quả."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from weather import KhoDuLieuThoiTiet


THU_MUC_GOC = Path(__file__).resolve().parents[1]

CAC_TRUY_VAN = [
    {"id": "Q01", "lat": 15.0, "lon": 110.2, "time_utc": "2024-10-10T12:00:00Z"},
    {"id": "Q02", "lat": 13.5, "lon": 110.2, "time_utc": "2024-10-12T06:00:00Z"},
    {"id": "Q03", "lat": 18.5, "lon": 108.5, "time_utc": "2024-10-14T00:00:00Z"},
    {"id": "Q04_OUTSIDE_SPACE", "lat": 25.0, "lon": 115.0, "time_utc": "2024-10-12T00:00:00Z"},
    {"id": "Q05_OUTSIDE_TIME", "lat": 15.0, "lon": 110.2, "time_utc": "2024-10-20T00:00:00Z"},
]


def main():
    # Cau hinh Terminal UTF-8 de hien thi tieng Viet co dau.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cac_ket_qua = []
    with KhoDuLieuThoiTiet() as kho_du_lieu:
        for truy_van in CAC_TRUY_VAN:
            ket_qua = kho_du_lieu.weather_at(truy_van["lat"], truy_van["lon"], truy_van["time_utc"])
            cac_ket_qua.append({"id": truy_van["id"], **ket_qua})

    duong_dan_ket_qua = THU_MUC_GOC / "outputs" / "weather_queries.json"
    duong_dan_ket_qua.parent.mkdir(parents=True, exist_ok=True)
    duong_dan_ket_qua.write_text(json.dumps(cac_ket_qua, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(cac_ket_qua, indent=2, ensure_ascii=False))
    print(f"Wrote {duong_dan_ket_qua}")


if __name__ == "__main__":
    main()
