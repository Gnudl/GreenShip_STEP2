"""Kiểm thử bảng trình bày kết quả không suy diễn tuyến tối ưu."""

from pathlib import Path
import sys


THU_MUC_GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(THU_MUC_GOC / "src"))

from result_table import tao_bang_ket_qua


def test_bang_giu_tuyen_khong_kha_thi_va_bo_fitness():
    bao_cao = {
        "routes": [
            {
                "route_id": "R02",
                "route_name": "Tuyến cắt đất",
                "distance_nm": 100.0,
                "duration_h": 10.0,
                "fuel_t": 2.0,
                "co2_t": 6.228,
                "feasible": False,
                "fitness": 2.0,
                "violations": {
                    "hard": [{"code": "LAND_CROSSING"}],
                    "soft": [],
                },
            }
        ]
    }
    bang = tao_bang_ket_qua(bao_cao)
    assert len(bang) == 1
    assert bool(bang.iloc[0]["feasible"]) is False
    assert bang.iloc[0]["fitness"] is None
    assert bang.iloc[0]["violation_codes"] == "LAND_CROSSING"
    assert "không khả thi" in bang.iloc[0]["result_note"]


def test_bang_khong_goi_tuyen_kha_thi_la_toi_uu():
    bao_cao = {
        "routes": [
            {
                "route_id": "R01",
                "route_name": "Tuyến tham chiếu",
                "distance_nm": 100.0,
                "duration_h": 10.0,
                "fuel_t": 2.0,
                "co2_t": 6.228,
                "feasible": True,
                "fitness": 2.0,
                "violations": {"hard": [], "soft": []},
            }
        ]
    }
    bang = tao_bang_ket_qua(bao_cao)
    assert bang.iloc[0]["fitness"] == 2.0
    assert "chưa phải tuyến tối ưu" in bang.iloc[0]["result_note"]
