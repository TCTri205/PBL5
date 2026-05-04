# Kế Hoạch Triển Khai Tích Hợp Phần Cứng (Hardware Integration Plan)

Tài liệu này xác định các bước cụ thể (actionable steps) để đưa hệ thống điều khiển băng chuyền (L298N) và cảm biến (E18-D80NK) vào hệ thống PBL5 hiện tại. Đảm bảo tính nhất quán với codebase `asyncio` và cấu trúc dự án.

## Giai đoạn 1: Chuẩn bị Môi trường & Chẩn đoán

**Task 1: Cập nhật thư viện (`requirements.txt` & `pi_edge/requirements.txt`)**
- **Hành động**: Thêm dòng `gpiozero` vào cả hai file để đảm bảo tính nhất quán giữa môi trường root và môi trường edge.

**Task 2: Cập nhật Unit Tests & Mocking (`tests/`)**
- **Mục tiêu**: Đảm bảo lệnh `python runner.py` không bị lỗi do không có phần cứng thật.
- **Hành động**: 
  - Cập nhật `tests/test_streamer.py`: Sử dụng `unittest.mock` để giả lập `ConveyorController`.
  - Cập nhật `tests/test_server.py`: Kiểm tra xem server có xử lý đúng payload có thêm trường `conveyor_status` không.

**Task 3: Cập nhật Tool kiểm tra (`pi_edge/check_hardware.py`)**
- **Hành động**: Bổ sung `import gpiozero` vào `check_dependencies()`.

---

## Giai đoạn 2: Phát triển Module Lõi

**Task 3: Khởi tạo Trình điều khiển Băng chuyền (`pi_edge/conveyor_controller.py`)**
- **Mục tiêu**: Tạo class độc lập để quản lý Motor và Sensor.
- **Hành động**: Tạo file mới.
- **Đặc tả Code**:
  - Khai báo class `ConveyorController` với `motor_fwd_pin=22`, `motor_bwd_pin=23`, `sensor_pin=17`.
  - Khởi tạo `Motor` và `DigitalInputDevice(pull_up=True)` từ `gpiozero`.
  - Định nghĩa property: `has_object -> bool` trả về `self.sensor.is_active` (True = có vật cản, vì `pull_up=True` là active-low).
  - Định nghĩa các method: `start()`, `stop()`, `shutdown()`.
  - Định nghĩa hàm async: `async def wait_for_object(self, timeout=30.0)`: Chờ cho đến khi sensor bị che.
  - Định nghĩa hàm async: `async def wait_until_clear(self, timeout=5.0)`: Chờ cho đến khi vật thể đi qua hết. **Timeout mặc định là 5.0 giây**.
  - **MỚI**: Thêm cơ chế `_wait_for_clear_safe` (trong streamer) để giới hạn số lần thử lại (mặc định 3 lần), tránh chạy motor vô hạn nếu kẹt vật.

---

## Giai đoạn 3: Tích hợp vào Pipeline Chính

**Task 4: Nâng cấp luồng xử lý Camera (`pi_edge/cam_stream.py`)**
- **Mục tiêu**: Chuyển từ "chụp liên tục" sang "chụp theo sự kiện".
- **Hành động**:
  - **4.1**: Import `ConveyorController`.
  - **4.2**: Trong `CameraStreamer.__init__`, thêm tham số `capture_delay` và `resume_delay`, đồng thời khởi tạo `self.conveyor = ConveyorController()`. **Lưu ý quan trọng**: `ConveyorController` được khởi tạo tại đây để tồn tại suốt vòng đời của đối tượng `streamer`, không bị khởi tạo lại khi mất kết nối.
  - **4.3**: Thay đổi logic trong `run_pipeline()`:
    - Bật băng chuyền (`self.conveyor.start()`).
    - Gọi `await self.conveyor.wait_for_object()`.
    - Dừng băng chuyền (`self.conveyor.stop()`).
    - Đợi quả ổn định (`await asyncio.sleep(self.capture_delay)`).
    - Capture ảnh, gọi `self.classifier.predict`.
    - **Reliable Send**: Thử gửi kết quả 3 lần. Nếu thất bại hoàn toàn, dừng băng chuyền và break loop để bảo vệ dữ liệu.
    - Bật lại băng chuyền, đợi quả đi qua (`await asyncio.sleep(self.resume_delay)`).
    - **MỚI**: Gọi `await self._wait_for_clear_safe()` để chắc chắn vùng cảm biến đã trống. Nếu vẫn kẹt sau 3 lần thử, thực hiện **Emergency Stop**.
  - **4.4**: Trong `send_result()`, bổ sung key `"conveyor_status": "stopped"` vào JSON payload.
  - **4.5**: Trong `cleanup()`, chỉ giải phóng Camera/WebSocket.
  - **4.6**: Trong `main()`, bọc vòng lặp reconnect bằng khối `try...finally`. Trong `finally`, gọi `streamer.conveyor.shutdown()` để đảm bảo GPIO luôn được giải phóng khi tắt script.
  - **4.7**: Bổ sung flag `--capture-delay`, `--resume-delay`, và `--clear-timeout` vào argument parser.

*(Lưu ý: File `start_pi.py` dùng `sys.argv[1:]` nên tự động hỗ trợ các tham số mới này, không cần sửa).*

---

## Giai đoạn 4: Cập nhật Server

**Task 5: Nâng cấp Server Giám sát (`laptop_server/server.py`)**
- **Mục tiêu**: Đọc và hiển thị trạng thái của phần cứng từ dưới Pi gửi lên.
- **Hành động**: 
  - Trong `fruit_classification_handler()`, lấy thêm trường `data.get("conveyor_status", "N/A")`.
  - Cập nhật dòng `logger.info(...)` để in ra trạng thái của băng chuyền, giúp dễ dàng debug từ xa.

---

## Giai đoạn 5: Kiểm thử (Validation)

- **Bước 1**: Chạy `python pi_edge/check_hardware.py` -> Đảm bảo `gpiozero` pass.
- **Bước 2**: Chạy `python start_server.py` trên Laptop.
- **Bước 3**: Chạy `python start_pi.py --capture-delay 0.3` trên Pi.
- **Bước 4**: Thử đưa vật thể (tay / trái cây) qua cảm biến E18-D80NK và theo dõi xem có tự động chụp và gửi dữ liệu lên server hay không.
