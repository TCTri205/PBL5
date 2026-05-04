# Kế Hoạch Triển Khai Tích Hợp Phần Cứng (Hardware Integration Plan)

Tài liệu này xác định các bước cụ thể (actionable steps) để đưa hệ thống điều khiển băng chuyền (L298N) và cảm biến (E18-D80NK) vào hệ thống PBL5 hiện tại. Đảm bảo tính nhất quán với codebase `asyncio` và cấu trúc dự án.

## Giai đoạn 1: Chuẩn bị Môi trường & Chẩn đoán

**Task 1: Cập nhật thư viện (`requirements.txt`)**
- **Mục tiêu**: Bổ sung thư viện điều khiển GPIO.
- **Hành động**: Thêm dòng `gpiozero` vào cuối file `requirements.txt`.

**Task 2: Cập nhật Tool kiểm tra (`pi_edge/check_hardware.py`)**
- **Mục tiêu**: Đảm bảo thư viện GPIO sẵn sàng trước khi chạy.
- **Hành động**: Trong hàm `check_dependencies()`, bổ sung `import gpiozero` vào khối try-except để verify.

---

## Giai đoạn 2: Phát triển Module Lõi

**Task 3: Khởi tạo Trình điều khiển Băng chuyền (`pi_edge/conveyor_controller.py`)**
- **Mục tiêu**: Tạo class độc lập để quản lý Motor và Sensor.
- **Hành động**: Tạo file mới.
- **Đặc tả Code**:
  - Khai báo class `ConveyorController` với `motor_fwd_pin=22`, `motor_bwd_pin=23`, `sensor_pin=17`.
  - Khởi tạo `Motor` và `DigitalInputDevice(pull_up=True)` từ `gpiozero`.
  - Định nghĩa property: `has_object -> bool` trả về `self.sensor.is_active` (True = có vật cản, vì `pull_up=True` là active-low).
  - Định nghĩa các method: `start()`, `stop()`, `shutdown()` (trong `shutdown()` phải gọi `sensor.close()` rồi mới `motor.close()`).
  - Định nghĩa hàm async: `async def wait_for_object(self, timeout=30.0)` chứa vòng lặp `while not self.sensor.is_active` với `await asyncio.sleep(0.05)` (non-blocking). **Timeout mặc định là 30.0 giây** (nhất quán với cách gọi trong `run_pipeline`).

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
    - Capture ảnh, gọi `self.classifier.predict`, gửi kết quả.
    - Bật lại băng chuyền, đợi quả đi qua (`await asyncio.sleep(self.resume_delay)`).
  - **4.4**: Trong `send_result()`, bổ sung key `"conveyor_status": "stopped"` vào JSON payload. **Giải thích**: Tại thời điểm `send_result()` được gọi, băng chuyền luôn ở trạng thái dừng (đã dừng trước khi chụp). Giá trị tĩnh `"stopped"` là đúng — không cần truyền tham số thêm.
  - **4.5**: Trong `cleanup()`, chỉ giải phóng các tài nguyên tạm thời (Camera, WebSocket). **KHÔNG** gọi `shutdown()` của conveyor tại đây để tránh làm hỏng GPIO khi reconnect.
  - **4.6**: Trong `main()` (argument parser), bổ sung flag `--capture-delay` (mặc định 0.2s) và `--resume-delay` (mặc định 1.0s). Truyền 2 tham số này vào class `CameraStreamer`.
  - **4.7**: Trong hàm xử lý thoát `handle_exit()` hoặc khối `finally` cuối cùng của `asyncio.run(main())`, bổ sung lệnh `streamer.conveyor.shutdown()` để đảm bảo giải phóng GPIO an toàn khi tắt chương trình.

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
