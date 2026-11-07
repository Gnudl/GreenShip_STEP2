# GreenShip STEP 2

Nhóm Hải Thần xây dựng nền tảng đánh giá tuyến Hải Phòng – Cái Mép bằng dữ liệu gió, sóng, dòng chảy và polygon đất liền. Ba tuyến thủ công dùng chung `evaluate_route()` để kiểm tra khả thi, tính quãng đường, thời gian, nhiên liệu và CO₂ ước tính.

## Cài đặt

Cài Python 3.10 trở lên, tải repo và mở thư mục gốc GreenShip_STEP2 trong VS Code. Mọi lệnh dưới đây chạy tại thư mục có README này.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Chọn interpreter `.venv\Scripts\python.exe` trong VS Code. Nếu Terminal chưa kích hoạt môi trường, thay `python` trong các lệnh bên dưới bằng `.\.venv\Scripts\python.exe`.

## Cấu trúc

```text
config/                  Kịch bản, thông số tàu và ràng buộc
data/raw/                Ba file thời tiết gốc
data/processed/          wind.nc, waves.nc, currents.nc
data/land/               Natural Earth Land 5.1.1
data/routes/             manual_routes.json
data/source_register.csv Nguồn, URL, phiên bản, ngày tải, giấy phép
src/                     Đọc dữ liệu, bản đồ, evaluator
tests/                   Kiểm thử tự động và script in bảng
outputs/maps/            Bản đồ vùng, ba tuyến, nền sóng Hs
outputs/tables/          Bảng kết quả CSV/PNG
outputs/                 Báo cáo JSON và log kiểm thử
screenshots/             Ảnh Terminal/giao diện do nhóm tự chụp
reports/                 Ghi nhận quyết định kịch bản
```

## Kịch bản và dữ liệu

- Điểm tiếp cận Hải Phòng `(106.8333, 20.6667)` và Cái Mép `(107.08, 10.42)` theo thứ tự kinh độ, vĩ độ WGS84. Các điểm là giả định nghiên cứu.
- Khởi hành `2024-10-10T00:00:00Z`, tương đương 07:00 giờ Việt Nam. Bbox `[105, 111, 9, 22]` theo `[west, east, south, north]`.
- ERA5 gió `u10/v10`, lưới 0,25°, đơn vị m/s. Sóng `swh`, lưới 0,5°, đơn vị m. Cả hai theo giờ, từ 10/10/2024 00:00 đến 14/10/2024 23:00 UTC.
- Dòng chảy Copernicus Marine `uo/vo`, khoảng 1/12°, trung bình ngày, đơn vị m/s. Lớp mặt khoảng 0,494025 m. Coverage từ 10/10/2024 00:00 đến 14/10/2024 00:00 UTC. Kinh độ thực tế 105.000015–110.916679°E.
- Natural Earth Land phiên bản 5.1.1, tỷ lệ 1:10 triệu. Giữ đầy đủ các thành phần shapefile trong `data/land/ne_10m_land/`.

Repo có dữ liệu gốc và ba NetCDF chuẩn hóa. Các ô thiếu được giữ là `NaN`. Metadata và điều kiện sử dụng theo từng nguồn nằm trong `data/source_register.csv`.

## Chạy lại

### 1. Kiểm tra dữ liệu

```powershell
python src\inspect_data.py
python src\read_processed.py
python src\check_weather.py
python src\map_domain.py
```

Nếu cần tạo lại dữ liệu chuẩn hóa từ raw, chạy `python src\normalize_data.py` trước `read_processed.py`. Lệnh chuẩn hóa ghi lại các tệp tương ứng trong `data/processed/`.

### 2. Hình học và tuyến

```powershell
python src\route_geometry.py
python src\map_manual_routes.py
python src\constraints.py
```

R01 là tuyến tham chiếu thủ công, R02 cố ý cắt đất, R03 là tuyến thay thế ngoài khơi. Tổng waypoint 11/5/11, tương ứng 9/3/9 điểm giữa. JSON tuyến là nguồn tọa độ khi chạy. `intermediate_waypoint_count: 2` trong YAML là ghi nhận ban đầu còn cần đồng bộ sau khi nhóm chốt số điểm với giảng viên.

`constraints_report.json` chỉ kiểm hình học và đường vòng. Evaluator bổ sung kiểm tra thời tiết.

### 3. Evaluator và bảng kết quả

```powershell
python src\evaluator.py
python src\result_table.py
python src\ve_ban_do_song.py
```

Các đầu ra gồm `outputs/evaluation_results.json`, `outputs/tables/route_results.csv`, `outputs/tables/route_results.png` và `outputs/maps/manual_routes_hs.png`. JSON chứa từng segment và khoảng mẫu. Hình Hs dùng dữ liệu tại giờ xuất phát và ghi UTC, đơn vị, nguồn.

Các script ghi lại đầu ra cùng tên. Muốn giữ một lần chạy làm bằng chứng, sao chép kết quả hoặc lưu bằng tên có ngày giờ trước lần chạy tiếp theo.

### 4. Kiểm thử

```powershell
python -m pytest -q
```

Lưu một log có ngày giờ trong PowerShell nếu cần:

```powershell
$thoiDiem = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
python -m pytest -q 2>&1 | Tee-Object -FilePath "outputs\pytest_$thoiDiem.txt"
```

Log đính kèm ở `outputs/test_results.txt`. Nhóm tự chụp Terminal đọc dữ liệu và pytest rồi lưu vào `screenshots/`. Hình chương trình xuất nằm trong `outputs/`.

### 5. Xem bảng dữ liệu

```powershell
python tests\print_processed_data.py --file wind --rows 20
python tests\print_processed_data.py --file waves --all
python tests\print_processed_data.py --file currents --all
```

`--all` in mọi dòng, kể cả ô thiếu. Terminal có thể giới hạn lịch sử hiển thị. Các bảng CSV đầy đủ có thể xuất lại từ NetCDF khi cần xem trong Excel.

## Cách đánh giá

- Khoảng cách dùng Vincenty inverse WGS84, 1 NM = 1852 m. Điểm mẫu nội suy cung lớn trên cầu, kiểm lại để khoảng cách WGS84 liên tiếp tối đa 5 NM.
- `weather_at()` kiểm miền không gian/thời gian rồi chọn mẫu gần nhất. Gió/sóng bắt buộc, dòng chảy tùy chọn.
- Nếu ô sóng gần nhất thiếu, chọn ô swh hữu hạn gần nhất trong 30 NM tại thời điểm đã chọn. Ghi tọa độ nguồn, phương pháp và khoảng cách. Nếu vẫn thiếu, tuyến invalid. Bán kính 30 NM là giả định mô hình.
- Thiếu dòng chảy thì SOG=STW và `current_applied=False`. Khi đủ uo/vo, chiếu dòng lên hướng đi để hiệu chỉnh SOG.
- Hard constraints gồm cắt đất, thiếu thời tiết bắt buộc, đoạn gần bằng 0, spacing sai và SOG không dương. Soft constraints gồm sóng trên 2 m và độ dài vượt 1,05 lần R01.
- Có hard violation thì `feasible=False`, `fitness=None`. Tuyến khả thi có fitness bằng `fuel_t`. Soft violations được lưu riêng, chưa cộng vào fitness.

## Thông số mô hình

`config/ship.json` ghi tàu giả định Handysize 40.000 DWT, STW=12 kn, công suất=5.000 kW, SFOC=190 g/kWh, HFO và CF tạm dùng 3,114 tCO₂/t-fuel.

```text
duration_h = distance_nm / SOG_kn
fuel_t = sum(power_kw * sfoc_g_per_kwh * duration_h) / 1_000_000
co2_t = fuel_t * CF
```

Ví dụ kiểm toán học riêng dùng 100 NM, 10 kn, 1.000 kW và SFOC 200 g/kWh, cho 10 h, 2 t nhiên liệu và 6,228 t CO₂.

## Kết quả đã lưu

| Tuyến | Distance (NM) | Giờ | Fuel (t) | CO₂ (t) | Khả thi |
|---|---:|---:|---:|---:|---|
| R01 | 779,602 | 62,689 | 59,555 | 185,453 | Có |
| R02 | 631,375 | 52,372 | 49,753 | 154,932 | Không |
| R03 | 822,731 | 68,036 | 64,634 | 201,271 | Có |

Nguồn là `outputs/evaluation_results.json`. Các giá trị R02 phục vụ chẩn đoán tuyến bị loại. R03 có soft violation đường vòng. Baseline là R01 thủ công khả thi trong mô hình. Rhumb Line giữ hướng và không mặc nhiên ngắn nhất.

## Giới hạn và việc còn cần nghiệm thu

- Fuel và CO₂ là ước tính toy model. Công suất/SFOC cố định, CF cần đối chiếu nguồn, CO₂ chỉ xét tank-to-wake.
- Gió/sóng chưa hiệu chỉnh tốc độ hoặc công suất. Dòng chảy chỉ chiếu dọc tuyến, chưa tính điều chỉnh hướng lái do dòng ngang.
- Quy tắc ô sóng 30 NM chưa kiểm kết nối biển qua đất và chưa đánh giá độ nhạy. Độ phân giải không gian/thời gian khác nhau giữa các nguồn.
- Natural Earth phục vụ sàng lọc nghiên cứu. Chưa xét độ sâu, mớn nước, vùng cấm và luồng cảng. Kết quả không dùng cho điều hướng thực tế.
- Truy vấn thời tiết tại đầu khoảng mẫu. Cần kiểm riêng thời tiết/coverage tại ETA cuối. `expected_max_duration_h: 72` là kỳ vọng, chưa thực thi thành hard constraint.
- Cần thống nhất số waypoint giữa trong YAML/JSON/báo cáo. Ghi nhận cũ trong `reports/` cần đọc cùng cấu hình và JSON hiện tại.
- `src/readdata.py` giữ theo bản đã có trên repo. Workflow hiện tại dùng `src/inspect_data.py`. Script cũ có thể ghi hình vào `screenshots/`, cần lưu ảnh Terminal bằng tên riêng.
- Còn cần ảnh chụp thật và xác nhận cả ba thành viên giải thích được luồng dữ liệu, lỗi minh họa. Chỉ triển khai COA/RIME/hybrid ở STEP 3 sau nghiệm thu và xử lý các vấn đề ảnh hưởng tính đúng.
